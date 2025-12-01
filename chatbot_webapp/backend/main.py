from fastapi import FastAPI, Request, Depends # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from pydantic import BaseModel # type: ignore
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
import re
import uuid
import logging
# from starlette.middleware.base import BaseHTTPMiddleware  # 로깅 미들웨어 사용 안 함
# 임베디드 벡터 검색을 위한 FAISS 사용
import numpy as np # type: ignore
import faiss # type: ignore
import pickle
from sentence_transformers import SentenceTransformer # type: ignore
from fastapi.staticfiles import StaticFiles # type: ignore
from fastapi.responses import HTMLResponse # type: ignore
from pathlib import Path
import sys
import asyncio
from asgiref.sync import sync_to_async # type: ignore
from typing import Optional

# Google의 Gemini API 통합
import google.generativeai as genai # type: ignore

# API 키 설정
GEMINI_API_KEY = "AIzaSyC-J3EZmtWoNiPJ7yzCwwAvY6ta5uny_9M"
genai.configure(api_key=GEMINI_API_KEY)

# Django 프로젝트 루트 경로를 Python 경로에 추가
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oncall_system.settings")

# Django 설정 초기화
try:
    import django # type: ignore
    django.setup()
    print("✅ Django 설정 초기화 완료")
except Exception as django_error:
    print(f"❌ Django 설정 초기화 실패: {django_error}")
    print(f"   프로젝트 루트 경로: {project_root}")
    print(f"   현재 작업 디렉토리: {os.getcwd()}")
    print(f"   Python 경로: {sys.path[:3]}...")
    import traceback
    traceback.print_exc()
    # Django 초기화가 실패해도 FastAPI는 시작할 수 있도록 계속 진행

# 챗봇 대화 로깅 시스템 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# 로그 디렉토리 강제 생성
def ensure_log_directories():
    """로그 디렉토리들을 강제로 생성"""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    log_directories = [
        "logs/django/access",
        "logs/django/api", 
        "logs/django/error",
        "logs/django/debug",
        "logs/fastapi/access",
        "logs/fastapi/api",
        "logs/fastapi/error", 
        "logs/fastapi/debug",
        "logs/fastapi/chatbot",
        "logs/system/startup",
        "logs/system/performance",
        "logs/system/security"
    ]
    
    for directory in log_directories:
        log_path = os.path.join(base_dir, directory)
        os.makedirs(log_path, exist_ok=True)
        print(f"📁 로그 디렉토리 생성: {log_path}")

# 로그 디렉토리 먼저 생성
ensure_log_directories()

try:
    from logs.logging_config import create_logger, log_api_request, log_system_startup, log_performance_metric, log_chatbot_conversation
    print("✅ 로깅 시스템이 성공적으로 로드되었습니다.")
    chatbot_log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs", "fastapi", "chatbot"))
    print(f"📁 챗봇 대화 로그 저장 경로: {chatbot_log_path}")
    LOGGING_ENABLED = True
except Exception as e:
    print(f"⚠️ 로깅 시스템 로드 실패: {e}")
    import traceback
    traceback.print_exc()
    print("📝 강화된 기본 로깅으로 계속 진행합니다.")
    LOGGING_ENABLED = False
    
    # 강화된 더미 함수들
    def create_logger(name, backend, log_type, level=None):
        return logging.getLogger(name)
    def log_api_request(logger, request_data):
        pass
    def log_system_startup(backend_name, version=None):
        print(f"🚀 {backend_name} 서버 시작됨")
        # 시스템 시작 로그도 파일에 기록
        try:
            log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "system", "startup")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"system_startup_{datetime.now().strftime('%Y-%m-%d')}.txt")
            with open(log_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {backend_name} 서버 시작됨 (더미 로거)\n")
        except Exception as startup_error:
            print(f"시작 로깅 실패: {startup_error}")
    
    def log_performance_metric(metric_name, value, unit='ms'):
        pass
    
    def log_chatbot_conversation(session_id, user_message, bot_response, response_time, ip_address=None, entities=None):
        # 콘솔과 파일에 모두 기록
        print(f"💬 세션: {session_id[:8]}... | 질문: {user_message[:30]}... | 응답: {bot_response[:30]}... | {response_time:.0f}ms")
        
        # 강화된 파일 로깅
        try:
            log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "fastapi", "chatbot")
            os.makedirs(log_dir, exist_ok=True)
            
            # 여러 파일에 백업 저장
            today = datetime.now().strftime('%Y-%m-%d')
            log_files = [
                os.path.join(log_dir, f"chatbot_conversations_{today}.txt"),
                os.path.join(log_dir, f"fallback_chatbot_{today}.txt"),
                os.path.join(log_dir, f"backup_chatbot_{today}.log")
            ]
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_content = f"[{timestamp}] 세션:{session_id} | 사용자 질문: {user_message} | 봇 응답: {bot_response} | 응답시간: {response_time:.2f}ms | IP: {ip_address or 'unknown'}\n"
            
            # 모든 로그 파일에 기록
            for log_file in log_files:
                try:
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(log_content)
                except Exception as individual_error:
                    print(f"개별 파일 로깅 실패 {log_file}: {individual_error}")
                    
            print(f"✅ 챗봇 로그가 {len(log_files)}개 파일에 저장되었습니다: {log_dir}")
            
        except Exception as file_error:
            print(f"❌ 파일 로깅 완전 실패: {file_error}")
            import traceback
            traceback.print_exc()

# Django 모델 가져오기
try:
    from schedule.models import Schedule, Doctor, Department, WorkSchedule
    print("✅ Django 모델 import 완료")
    DJANGO_AVAILABLE = True
except Exception as model_error:
    print(f"❌ Django 모델 import 실패: {model_error}")
    print("   Django 연동 기능이 제한됩니다.")
    DJANGO_AVAILABLE = False
    # 더미 클래스들로 대체
    class Schedule: pass
    class Doctor: pass
    class Department: pass
    class WorkSchedule: pass

# 현재 시스템 시간 출력 (디버깅용)
current_time = datetime.now()
print(f"===== 시스템 현재 시간: {current_time} =====")
print(f"===== 현재 날짜: {current_time.strftime('%Y-%m-%d')} =====")
print(f"===== 현재 시간: {current_time.strftime('%H:%M:%S')} =====")
print(f"===== 시간대: {current_time.tzinfo} =====")

app = FastAPI()

# 세션별 대화 기록을 저장할 딕셔너리
session_conversations = {}

class ConversationContext:
    """대화 맥락을 저장하는 클래스"""
    def __init__(self):
        self.last_department = None
        self.last_role = None
        self.last_date = None
        self.last_doctor = None  # 마지막으로 언급된 의사 이름 (호환성 유지)
        self.last_doctors = []   # 마지막 응답에서 언급된 모든 의사들
        self.last_query = None
        self.last_response = None
        self.conversation_history = []
    
    def update_context(self, entities, query, response):
        """대화 맥락 업데이트"""
        # 새로운 일반 질문이 들어오면 이전 의사 맥락 초기화
        if entities.get('department') and not entities.get('contact_request'):
            # 부서 질문이고 연락처 요청이 아닌 경우 의사 맥락 초기화
            print(f"새로운 부서 질문으로 의사 맥락 초기화: {entities.get('department')}")
            self.last_doctor = None
            self.last_doctors = []
        
        if entities.get('department'):
            self.last_department = entities['department']
        if entities.get('role'):
            self.last_role = entities['role']
        if entities.get('date'):
            self.last_date = entities['date']
        if entities.get('doctor_name'):
            self.last_doctor = entities['doctor_name']
            # 새로운 의사가 추가되면 이전 의사들 목록 초기화하고 새 의사만 저장
            self.last_doctors = [entities['doctor_name']]
        if entities.get('doctor_names'):
            self.last_doctors = entities['doctor_names']
            # 호환성을 위해 첫 번째 의사를 last_doctor에도 설정
            if self.last_doctors:
                self.last_doctor = self.last_doctors[0]
        
        self.last_query = query
        self.last_response = response
        
        # 대화 기록에 추가
        self.conversation_history.append({
            'query': query,
            'response': response,
            'timestamp': datetime.now().isoformat(),
            'entities': entities
        })
        
        # 대화 기록이 너무 길어지면 오래된 것 삭제 (최대 10개)
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
    
    def get_context_info(self):
        """현재 맥락 정보 반환"""
        return {
            'last_department': self.last_department,
            'last_role': self.last_role,
            'last_date': self.last_date,
            'last_doctor': self.last_doctor,
            'last_doctors': self.last_doctors,
            'last_query': self.last_query
        }

def get_or_create_session_context(session_id):
    """세션별 대화 맥락 가져오기 또는 생성"""
    if session_id not in session_conversations:
        session_conversations[session_id] = ConversationContext()
    return session_conversations[session_id]

def is_follow_up_question(message: str):
    """후속 질문인지 판단하는 함수"""
    follow_up_patterns = [
        # n일 후/뒤/전 패턴 (가장 구체적인 것부터)
        (r'^\d+일\s*(?:후|뒤).*\?*$', 'n일_후_패턴'),
        (r'^\d+일\s*전.*\?*$', 'n일_전_패턴'),
        (r'^그럼\s*\d+일\s*(?:후|뒤).*\?*$', '그럼_n일_후_패턴'),
        (r'^그럼\s*\d+일\s*전.*\?*$', '그럼_n일_전_패턴'),
        (r'^그러면\s*\d+일\s*(?:후|뒤).*\?*$', '그러면_n일_후_패턴'),
        (r'^그러면\s*\d+일\s*전.*\?*$', '그러면_n일_전_패턴'),
        
        # 주차 + 요일 조합 패턴
        (r'^(이번주|다음주|저번주|지난주|다다음주)\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)은\?*$', '주차_요일_조합'),
        (r'^(이번주|다음주|저번주|지난주|다다음주)\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)\?*$', '주차_요일_조합_2'),
        (r'^그럼\s*(이번주|다음주|저번주|지난주|다다음주)\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)은\?*$', '그럼_주차_요일_조합'),
        (r'^그럼\s*(이번주|다음주|저번주|지난주|다다음주)\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)\?*$', '그럼_주차_요일_조합_2'),
        (r'^그러면\s*(이번주|다음주|저번주|지난주|다다음주)\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)은\?*$', '그러면_주차_요일_조합'),
        (r'^그러면\s*(이번주|다음주|저번주|지난주|다다음주)\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)\?*$', '그러면_주차_요일_조합_2'),
        
        # 기본 후속 질문 패턴
        (r'^내일은\?*$', '내일_패턴'),
        (r'^내일모레는\?*$', '내일모레_패턴'),
        (r'^내일모레\?*$', '내일모레_단순_패턴'),
        (r'^다음주는\?*$', '다음주_패턴'),
        (r'^이번주는\?*$', '이번주_패턴'),
        (r'^저번주는\?*$', '저번주_패턴'),
        (r'^지난주는\?*$', '지난주_패턴'),
        (r'^어제는\?*$', '어제_패턴'),
        (r'^모레는\?*$', '모레_패턴'),
        (r'^글피는\?*$', '글피_패턴'),
        (r'^다다음주는\?*$', '다다음주_패턴'),
        
        # "그럼/그러면" 접두사가 있는 패턴
        (r'^그럼\s*(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)는\?*', '그럼_시간_패턴'),
        (r'^그럼\s*(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)\?*$', '그럼_시간_단순_패턴'),
        (r'^그럼\s*(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)은\?*$', '그럼_시간_은_패턴'),
        (r'^그럼\s*(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)\s*당직은\?*', '그럼_시간_당직_패턴'),
        (r'^그러면\s*(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)는\?*', '그러면_시간_패턴'),
        (r'^그러면\s*(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)\?*$', '그러면_시간_단순_패턴'), 
        (r'^그러면\s*(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)은\?*$', '그러면_시간_은_패턴'),
        (r'^그러면\s*(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)\s*당직은\?*', '그러면_시간_당직_패턴'),
        
        # "당직은" 접미사가 있는 패턴
        (r'^(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)\s*당직은\?*', '시간_당직_패턴'),
        (r'^(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)은\?*', '시간_은_패턴'),
        (r'^(내일|다음주|이번주|저번주|지난주|어제|모레|글피|다다음주)\?*$', '시간_단순_패턴'),
        
        # 요일 패턴
        (r'^(월요일|화요일|수요일|목요일|금요일|토요일|일요일)은\?*$', '요일_은_패턴'),
        (r'^(월요일|화요일|수요일|목요일|금요일|토요일|일요일)\?*$', '요일_단순_패턴'),
        (r'^그럼\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)은\?*', '그럼_요일_패턴'),
        (r'^그럼\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)\?*$', '그럼_요일_단순_패턴'),
        (r'^그럼\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)\s*당직은\?*', '그럼_요일_당직_패턴'),
        (r'^그러면\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)은\?*', '그러면_요일_패턴'),
        (r'^그러면\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)\?*$', '그러면_요일_단순_패턴'),
        (r'^그러면\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)\s*당직은\?*', '그러면_요일_당직_패턴'),
        
        # 날짜 형식 패턴
        (r'^\d{4}-\d{1,2}-\d{1,2}\?*$', '전체_날짜_패턴'),
        (r'^\d{4}\/\d{1,2}\/\d{1,2}\?*$', '전체_날짜_슬래시_패턴'),
        (r'^\d{1,2}-\d{1,2}\?*$', '월일_대시_패턴'),
        (r'^\d{1,2}\/\d{1,2}\?*$', '월일_슬래시_패턴'),
        (r'^\d{1,2}월\s*\d{1,2}일\?*$', '한국_날짜_패턴'),
        (r'^\d{1,2}일\?*$', '일_단위_패턴'),
        
        # 간단한 질문 패턴
        (r'^그날은\?*$', '그날_패턴'),
        (r'^언제\?*$', '언제_패턴'),
        (r'^몇일\?*$', '몇일_패턴'),
        (r'^며칠\?*$', '며칠_패턴'),
        
        # 연락처 관련 패턴
        (r'^연락처\s*알려줘\?*$', '연락처_질문'),
        (r'^연락처\s*뭐야\?*$', '연락처_질문_2'),
        (r'^연락처는\?*$', '연락처_질문_3'),
        (r'^전화번호\s*알려줘\?*$', '전화번호_질문'),
        (r'^전화번호\s*뭐야\?*$', '전화번호_질문_2'),
        (r'^전화번호는\?*$', '전화번호_질문_3')
    ]
    
    message_clean = message.strip()
    print(f"     후속 질문 패턴 체크 - 입력: '{message_clean}'")
    
    for i, (pattern, pattern_name) in enumerate(follow_up_patterns):
        if re.search(pattern, message_clean, re.IGNORECASE):
            print(f"     ✅ 패턴 {i+1} 매치: {pattern_name} - {pattern}")
            return True
    
    print(f"     ❌ 후속 질문 패턴에 매치되지 않음")
    return False


# =============================================================================
# 부서 추천 함수들
# =============================================================================

def find_similar_departments(query_dept: str, all_departments: list) -> list:
    """사용자 질문에서 추출한 부서명과 유사한 실제 부서들을 찾아 추천"""
    if not query_dept or not all_departments:
        return []
    
    similar_depts = []
    query_lower = query_dept.lower()
    
    print(f"🔍 부서 추천 검색: '{query_dept}'")
    print(f"   전체 부서 수: {len(all_departments)}개")
    
    # 1. 부분 매칭 - 질문한 단어가 부서명에 포함된 경우
    for dept in all_departments:
        if query_dept in dept:
            similar_depts.append(dept)
            print(f"   ✅ 부분 매칭: '{dept}' ('{query_dept}' 포함)")
    
    # 2. 키워드 기반 매칭
    keyword_mappings = {
        '외과': ['외과', '수술'],
        '내과': ['내과', '내시경'],
        '소아': ['소아', '아이', '어린이'],
        '정신': ['정신', '심리'],
        '피부': ['피부', '성형'],
        '안과': ['안과', '눈'],
        '이비인후과': ['이비인후과', '귀', '코', '목'],
        '산부인과': ['산부인과', '산과', '부인과', '여성'],
        '비뇨기과': ['비뇨기과', '비뇨'],
        '응급': ['응급', 'ER', '응급실'],
        '중환자': ['중환자', 'ICU', '집중치료'],
        '재활': ['재활', '물리치료'],
        '마취': ['마취', '수술'],
        '영상': ['영상', '방사선', 'CT', 'MRI'],
        '병리': ['병리', '검사']
    }
    
    # 키워드 매칭으로 추가 부서 찾기
    for keyword, related_words in keyword_mappings.items():
        if any(word in query_lower for word in related_words):
            for dept in all_departments:
                if keyword in dept and dept not in similar_depts:
                    similar_depts.append(dept)
                    print(f"   ✅ 키워드 매칭: '{dept}' (키워드: {keyword})")
    
    print(f"   📋 총 {len(similar_depts)}개 부서 발견: {similar_depts}")
    return similar_depts

def create_department_recommendation_response(query_dept: str, similar_depts: list) -> str:
    """부서 추천 응답 메시지 생성"""
    if not similar_depts:
        return f"죄송합니다. '{query_dept}'와 관련된 진료과를 찾을 수 없습니다."
    
    if len(similar_depts) == 1:
        # 하나만 발견된 경우
        return f"'{query_dept}'와 관련하여 **{similar_depts[0]}**을(를) 찾았습니다.\n\n다시 질문해 주세요:\n💡 예시: \"{similar_depts[0]} 당직 누구야?\""
    
    # 여러 개 발견된 경우
    response_lines = [f"'{query_dept}'와 관련된 여러 진료과를 찾았습니다:"]
    response_lines.append("")
    
    for i, dept in enumerate(similar_depts[:5], 1):  # 최대 5개까지만
        response_lines.append(f"{i}. **{dept}**")
    
    if len(similar_depts) > 5:
        response_lines.append(f"... 외 {len(similar_depts) - 5}개 더")
    
    response_lines.append("")
    response_lines.append("구체적인 진료과명으로 다시 질문해 주세요:")
    response_lines.append(f"💡 예시: \"{similar_depts[0]} 당직 누구야?\"")
    
    return "\n".join(response_lines)

def extract_follow_up_reference(message: str):
    """후속 질문에서 참조 정보 추출 (시간, 연락처 등)"""
    message_clean = message.strip()
    
    print(f"     후속 참조 추출 시작 - 입력: '{message_clean}'")
    
    # 연락처 관련 질문인지 먼저 확인
    contact_patterns = ['연락처', '전화번호']
    for pattern in contact_patterns:
        if pattern in message_clean:
            print(f"     ✅ 연락처 질문 감지: {pattern} → contact_request")
            return 'contact_request'
    
    # n일 후/뒤/전 패턴 먼저 확인
    days_later_pattern = re.search(r'(\d+)일\s*(?:후|뒤)', message_clean)
    if days_later_pattern:
        days = int(days_later_pattern.group(1))
        print(f"     ✅ n일 후 패턴 감지: {days}일")
        return f'days_later_{days}'
    
    days_before_pattern = re.search(r'(\d+)일\s*전', message_clean) 
    if days_before_pattern:
        days = int(days_before_pattern.group(1))
        print(f"     ✅ n일 전 패턴 감지: {days}일")
        return f'days_before_{days}'
    
    # "그럼", "그러면" 접두사 제거 (시간 키워드 추출을 위해)
    clean_message = message_clean
    if message_clean.startswith('그럼 '):
        clean_message = message_clean[3:].strip()
        print(f"     '그럼' 접두사 제거: '{clean_message}'")
    elif message_clean.startswith('그러면 '):
        clean_message = message_clean[4:].strip()
        print(f"     '그러면' 접두사 제거: '{clean_message}'")
    
    # 기본 시간 키워드
    time_patterns = {
        '내일': 'tomorrow',
        '내일모레': 'tomorrow_and_day_after_tomorrow',
        '다음주': 'next_week', 
        '이번주': 'this_week',
        '저번주': 'last_week',
        '지난주': 'last_week',
        '어제': 'yesterday',
        '모레': 'day_after_tomorrow',
        '글피': 'day_after_day_after_tomorrow',
        '다다음주': 'week_after_next'
    }
    
    # 주차 + 요일 조합 패턴 확인
    week_day_pattern = re.search(r'(이번주|다음주|저번주|지난주|다다음주)\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)', clean_message)
    if week_day_pattern:
        week_part = week_day_pattern.group(1)
        day_part = week_day_pattern.group(2)
        
        week_mapping = {
            '이번주': 'this_week',
            '다음주': 'next_week',
            '저번주': 'last_week',
            '지난주': 'last_week',
            '다다음주': 'week_after_next'
        }
        
        day_mapping = {
            '월요일': 'monday', '화요일': 'tuesday', '수요일': 'wednesday',
            '목요일': 'thursday', '금요일': 'friday', '토요일': 'saturday', '일요일': 'sunday'
        }
        
        time_ref = f"{week_mapping[week_part]}_{day_mapping[day_part]}"
        print(f"     ✅ 주차+요일 조합 감지: {week_part} {day_part} → {time_ref}")
        return time_ref
    
    # 단순 요일 패턴 확인
    weekday_pattern = re.search(r'(월요일|화요일|수요일|목요일|금요일|토요일|일요일)', clean_message)
    if weekday_pattern:
        day_part = weekday_pattern.group(1)
        day_mapping = {
            '월요일': 'monday', '화요일': 'tuesday', '수요일': 'wednesday',
            '목요일': 'thursday', '금요일': 'friday', '토요일': 'saturday', '일요일': 'sunday'
        }
        time_ref = f"next_{day_mapping[day_part]}"
        print(f"     ✅ 단순 요일 감지: {day_part} → {time_ref}")
        return time_ref
    
    # 날짜 형식 패턴 확인
    date_patterns = [
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'full_date'),      # 2025-07-25
        (r'(\d{4})\/(\d{1,2})\/(\d{1,2})', 'full_date_slash'), # 2025/7/25
        (r'(\d{1,2})-(\d{1,2})', 'month_day'),              # 07-25, 7-25
        (r'(\d{1,2})\/(\d{1,2})', 'month_day_slash'),       # 7/25, 07/25
        (r'(\d{1,2})월\s*(\d{1,2})일', 'korean_date'),       # 7월 25일
        (r'(\d{1,2})일', 'day_only')                        # 25일
    ]
    
    for pattern, pattern_type in date_patterns:
        match = re.search(pattern, message_clean)
        if match:
            if pattern_type in ['full_date', 'full_date_slash']:
                year, month, day = match.groups()
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            elif pattern_type in ['month_day', 'month_day_slash']:
                month, day = match.groups()
                year = datetime.now().year
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            elif pattern_type == 'korean_date':
                month, day = match.groups()
                year = datetime.now().year
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            elif pattern_type == 'day_only':
                day = match.group(1)
                today = datetime.now()
                month = today.month
                year = today.year
                date_str = f"{year}-{month:02d}-{day.zfill(2)}"
            
            print(f"     ✅ 날짜 형식 감지: {match.group(0)} → specific_date_{date_str}")
            return f"specific_date_{date_str}"
    
    # 기본 키워드 매칭 - 더 긴 키워드부터 우선 매칭
    time_patterns_ordered = [
        ('내일모레', 'tomorrow_and_day_after_tomorrow'),  # 먼저 체크
        ('다다음주', 'week_after_next'),
        ('글피', 'day_after_day_after_tomorrow'),
        ('내일', 'tomorrow'),
        ('다음주', 'next_week'), 
        ('이번주', 'this_week'),
        ('저번주', 'last_week'),
        ('지난주', 'last_week'),
        ('어제', 'yesterday'),
        ('모레', 'day_after_tomorrow')
    ]
    
    for keyword, time_ref in time_patterns_ordered:
        if keyword in clean_message:
            print(f"     ✅ 기본 키워드 감지: {keyword} → {time_ref}")
            return time_ref
    
    # "그날", "언제", "몇일" 등의 일반적인 질문
    if any(word in clean_message for word in ['그날', '언제', '몇일', '며칠']):
        print(f"     ⚠️ 일반적인 시간 질문 감지 - 기본값 사용")
        return 'general_time_question'
    
    print(f"     ❌ 시간 참조 추출 실패")
    return None

def calculate_from_follow_up_reference(time_ref):
    """후속 질문 참조로부터 정보 계산 (날짜, 연락처 등)"""
    today = datetime.now()
    print(f"===== 후속 참조 처리 시작 =====")
    print(f"     time_ref: '{time_ref}'")
    print(f"     현재 날짜: {today.strftime('%Y-%m-%d')}")
    
    try:
        # 연락처 요청 처리
        if time_ref == 'contact_request':
            print(f"     'contact_request' → 연락처 조회 요청")
            return 'contact_request'
        
        # 기본 시간 참조
        if time_ref == 'tomorrow':
            result_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"     'tomorrow' → {result_date}")
            return result_date
        elif time_ref == 'tomorrow_and_day_after_tomorrow':
            # 내일모레는 모레(day_after_tomorrow)와 동일하게 처리
            result_date = (today + timedelta(days=2)).strftime('%Y-%m-%d')
            print(f"     'tomorrow_and_day_after_tomorrow' → {result_date} (모레와 동일 처리)")
            return result_date
        elif time_ref == 'yesterday':
            result_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"     'yesterday' → {result_date}")
            return result_date
        elif time_ref == 'day_after_tomorrow':
            result_date = (today + timedelta(days=2)).strftime('%Y-%m-%d')
            print(f"     'day_after_tomorrow' → {result_date}")
            return result_date
        elif time_ref == 'day_after_day_after_tomorrow':  # 글피
            result_date = (today + timedelta(days=3)).strftime('%Y-%m-%d')
            print(f"     'day_after_day_after_tomorrow' → {result_date}")
            return result_date
        elif time_ref == 'this_week':
            # 이번주 같은 요일
            result_date = today.strftime('%Y-%m-%d')
            print(f"     'this_week' → {result_date}")
            return result_date
        elif time_ref == 'next_week':
            # 다음주 같은 요일
            result_date = (today + timedelta(weeks=1)).strftime('%Y-%m-%d')
            print(f"     'next_week' → {result_date}")
            return result_date
        elif time_ref == 'last_week':
            # 저번주 같은 요일
            result_date = (today - timedelta(weeks=1)).strftime('%Y-%m-%d')
            print(f"     'last_week' → {result_date}")
            return result_date
        elif time_ref == 'week_after_next':
            # 다다음주 같은 요일
            result_date = (today + timedelta(weeks=2)).strftime('%Y-%m-%d')
            print(f"     'week_after_next' → {result_date}")
            return result_date
        
        # n일 후 패턴  
        elif time_ref.startswith('days_later_'):
            days = int(time_ref.split('_')[2])
            result_date = (today + timedelta(days=days)).strftime('%Y-%m-%d')
            print(f"     'days_later_{days}' → {result_date}")
            return result_date
        
        # n일 전 패턴
        elif time_ref.startswith('days_before_'):
            days = int(time_ref.split('_')[2])
            result_date = (today - timedelta(days=days)).strftime('%Y-%m-%d')
            print(f"     'days_before_{days}' → {result_date}")
            return result_date
        
        # 구체적인 날짜 패턴
        elif time_ref.startswith('specific_date_'):
            date_str = time_ref.split('_', 2)[2]
            print(f"     'specific_date' → {date_str}")
            return date_str
        
        # 주차 + 요일 조합 패턴
        elif '_' in time_ref:
            parts = time_ref.split('_')
            
            # 다음주 월요일, 이번주 금요일 등
            if len(parts) >= 2:
                week_part = parts[0] + '_' + parts[1]  # this_week, next_week 등
                day_part = parts[-1] if len(parts) > 2 else None  # monday, tuesday 등
                
                weekday_map = {
                    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                    'friday': 4, 'saturday': 5, 'sunday': 6
                }
                
                # 주차 기준점 계산
                if week_part == 'this_week':
                    target_monday = today - timedelta(days=today.weekday())
                elif week_part == 'next_week':
                    target_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=1)
                elif week_part == 'last_week':
                    target_monday = today - timedelta(days=today.weekday()) - timedelta(weeks=1)
                elif week_part == 'week_after_next':
                    target_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=2)
                else:
                    print(f"     알 수 없는 주차 참조: '{week_part}'")
                    return None
                
                # 특정 요일이 지정된 경우
                if day_part and day_part in weekday_map:
                    target_weekday = weekday_map[day_part]
                    result_date = (target_monday + timedelta(days=target_weekday)).strftime('%Y-%m-%d')
                    print(f"     '{week_part}_{day_part}' → {result_date}")
                    return result_date
                # 단순 요일 (다음 해당 요일)
                elif parts[0] == 'next' and parts[1] in weekday_map:
                    target_weekday = weekday_map[parts[1]]
                    current_weekday = today.weekday()
                    
                    # 다음에 오는 해당 요일 계산
                    days_ahead = target_weekday - current_weekday
                    if days_ahead <= 0:  # 오늘이거나 이미 지났으면 다음주
                        days_ahead += 7
                    
                    result_date = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
                    print(f"     'next_{parts[1]}' → {result_date} ({days_ahead}일 후)")
                    return result_date
                else:
                    # 주차만 지정된 경우 (같은 요일)
                    if week_part == 'this_week':
                        result_date = today.strftime('%Y-%m-%d')
                    elif week_part == 'next_week':
                        result_date = (today + timedelta(weeks=1)).strftime('%Y-%m-%d')
                    elif week_part == 'last_week':
                        result_date = (today - timedelta(weeks=1)).strftime('%Y-%m-%d')
                    elif week_part == 'week_after_next':
                        result_date = (today + timedelta(weeks=2)).strftime('%Y-%m-%d')
                    else:
                        return None
                    
                    print(f"     '{week_part}' (같은 요일) → {result_date}")
                    return result_date
        
        # 일반적인 시간 질문
        elif time_ref == 'general_time_question':
            # 일반적인 시간 질문인 경우 내일로 기본 설정
            result_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"     'general_time_question' → {result_date} (기본값: 내일)")
            return result_date
        
        else:
            print(f"     알 수 없는 시간 참조: '{time_ref}'")
            return None
    except Exception as e:
        print(f"     날짜 계산 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return None

# 로깅 시스템 초기화
print("📋 로깅 시스템 초기화 중...")
try:
    access_logger = create_logger('fastapi_access', 'fastapi', 'access')
    api_logger = create_logger('fastapi_api', 'fastapi', 'api')
    error_logger = create_logger('fastapi_error', 'fastapi', 'error')
    debug_logger = create_logger('fastapi_debug', 'fastapi', 'debug')
    
    # 챗봇 로그 디렉토리 생성 및 확인
    chatbot_log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs", "fastapi", "chatbot"))
    os.makedirs(chatbot_log_dir, exist_ok=True)
    
    print("✅ 로깅 초기화 완료")
    print(f"📁 챗봇 대화 로그 저장 경로: {chatbot_log_dir}")
    
except Exception as e:
    print(f"⚠️ 로깅 초기화 중 오류: {e}")
    # 기본 로거들로 대체
    access_logger = logging.getLogger('fastapi_access')
    api_logger = logging.getLogger('fastapi_api')
    error_logger = logging.getLogger('fastapi_error')
    debug_logger = logging.getLogger('fastapi_debug')

# 복잡한 로깅 미들웨어 제거됨 - 간단한 콘솔 로깅만 사용

# 정적 파일 디렉토리 설정
static_dir = Path(__file__).parent / "static"
if not static_dir.exists():
    static_dir.mkdir(parents=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 모든 요청 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"🌐 요청 수신: {request.method} {request.url}")
    print(f"   클라이언트 IP: {request.client.host if request.client else 'unknown'}")
    response = await call_next(request)
    print(f"   응답 상태: {response.status_code}")
    return response

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 시스템 시작 로그
print("🚀 FastAPI 챗봇 백엔드 시작 중...")
log_system_startup('FastAPI', '0.1.0')
debug_logger.info("FastAPI 챗봇 백엔드가 시작되었습니다.")
print("✅ FastAPI 챗봇 백엔드 시작 완료!")

# 벡터 검색 설정
VECTOR_DB_PATH = "./vector_db.pkl"  # 벡터 및 메타데이터 저장 파일 (기존 파일 우선 호환)
VECTOR_DIM = 384  # SentenceTransformer 모델 출력 차원

# SentenceTransformer 모델 로드 - 성능 최적화를 위해 더 빠른 모델 사용
print("임베딩 모델 로딩 중...")
# 기존 모델 유지 (호환성 우선)
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')  # 기존 모델 유지
# model = SentenceTransformer('all-MiniLM-L6-v2')  # 속도 우선시 할 경우 사용 (차후 적용)

# GPU 사용 가능 여부 확인
import torch
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"사용할 디바이스: {device}")

# 모델을 GPU로 이동 (가능한 경우)
if torch.cuda.is_available():
    model = model.to(device)
    print("GPU 가속 활성화됨")
    # GPU 메모리 최적화
    torch.cuda.empty_cache()
else:
    print("CPU 모드로 실행")

print("임베딩 모델 로딩 완료!")

# 성능 최적화 설정 활성화
import os
os.environ['OMP_NUM_THREADS'] = '4'  # CPU 스레드 수 제한 (안정성)
os.environ['TOKENIZERS_PARALLELISM'] = 'false'  # 토크나이저 병렬화 비활성화 (충돌 방지)

# 성능 최적화를 위한 배치 크기 설정
# GPU 사용 시 더 큰 배치 크기로 설정
EMBEDDING_BATCH_SIZE = 500 if torch.cuda.is_available() else 100  # 성능 최적화된 배치 크기

# FAISS 인덱스 초기화 또는 로드
class FAISSVectorStore:
    def __init__(self, vector_dim):
        self.vector_dim = vector_dim
        self.index = None
        self.metadata = []  # 각 벡터에 대한 메타데이터 저장
        self.schedule_id_index = set()  # 스케줄 ID 빠른 조회용 인덱스 (O(1) 검색)
        self.load_or_create_index()
    
    def load_or_create_index(self):
        """저장된 인덱스를 로드하거나 새로운 인덱스 생성 - 기존 파일 호환성 우선"""
        if os.path.exists(VECTOR_DB_PATH):
            try:
                # 기존 비압축 파일 먼저 시도 (호환성 우선)
                with open(VECTOR_DB_PATH, 'rb') as f:
                    data = pickle.load(f)
                
                self.index = data['index']
                self.metadata = data['metadata']
                
                # 스케줄 ID 인덱스 복원 (기존 데이터 호환성)
                if 'schedule_id_index' in data:
                    self.schedule_id_index = data['schedule_id_index']
                else:
                    # 기존 메타데이터에서 스케줄 ID 인덱스 재구성
                    print("기존 파일에서 스케줄 ID 인덱스 재구성 중...")
                    self.schedule_id_index = {item.get('schedule_id') for item in self.metadata if item.get('schedule_id')}
                    print(f"스케줄 ID 인덱스 재구성 완료: {len(self.schedule_id_index)}개")
                
                print(f"기존 벡터 데이터베이스를 로드했습니다. 벡터 수: {len(self.metadata)}, 스케줄 ID: {len(self.schedule_id_index)}개")
                return
            except Exception as e:
                print(f"벡터 데이터베이스 로드 오류: {e}")
                print("새로운 벡터 데이터베이스를 생성합니다.")
        
        # 새로운 인덱스 생성
        self.index = faiss.IndexFlatIP(self.vector_dim)  # 내적(코사인 유사도) 사용
        self.metadata = []
        self.schedule_id_index = set()
        print("새로운 벡터 데이터베이스를 생성했습니다.")
    
    def save_index(self):
        """인덱스를 파일로 저장 - 기존 호환성 유지"""
        try:
            # 기존 형식으로 저장 (호환성 우선)
            with open(VECTOR_DB_PATH, 'wb') as f:
                pickle.dump({
                    'index': self.index, 
                    'metadata': self.metadata,
                    'schedule_id_index': self.schedule_id_index
                }, f, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"벡터 데이터베이스를 저장했습니다. 벡터 수: {len(self.metadata)}, 스케줄 ID: {len(self.schedule_id_index)}개")
        except Exception as e:
            print(f"벡터 데이터베이스 저장 오류: {e}")
    
    def add_vectors(self, vectors, metadata_list, incremental=False, save_immediately=True):
        """벡터와 메타데이터 추가 - 성능 최적화"""
        if len(vectors) == 0:
            return
        
        # 벡터를 numpy 배열로 변환
        vectors_np = np.array(vectors).astype('float32')
        
        if incremental and self.index.ntotal > 0:
            # 증분 업데이트: 기존 벡터 유지하면서 새로운 벡터 추가
            self.index.add(vectors_np)
            self.metadata.extend(metadata_list)
            # 스케줄 ID 인덱스 업데이트 - O(1) 연산으로 빠른 처리
            for item in metadata_list:
                if item.get('schedule_id'):
                    self.schedule_id_index.add(item['schedule_id'])
            print(f"{len(vectors)}개의 벡터를 기존 {self.index.ntotal - len(vectors)}개에 추가했습니다.")
        else:
            # 전체 교체: 기존 인덱스 삭제하고 새로 생성
            self.index = faiss.IndexFlatIP(self.vector_dim)
            self.metadata = metadata_list
            self.index.add(vectors_np)
            # 스케줄 ID 인덱스 재구성
            self.schedule_id_index = {item.get('schedule_id') for item in metadata_list if item.get('schedule_id')}
            print(f"{len(vectors)}개의 벡터를 새로 생성했습니다.")
        
        # 즉시 저장 옵션 (성능 최적화를 위해 나중에 저장 가능)
        if save_immediately:
            self.save_index()
    
    def search(self, query_vector, k=3):
        """벡터 검색"""
        if self.index.ntotal == 0:
            return []
        
        # 쿼리 벡터를 numpy 배열로 변환
        query_vector_np = np.array([query_vector]).astype('float32')
        
        # 검색 수행
        distances, indices = self.index.search(query_vector_np, k)
        
        # 결과 반환
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata) and idx >= 0:
                results.append({
                    "distance": float(distances[0][i]),
                    "entity": self.metadata[idx]
                })
        
        return results

# 벡터 스토어 초기화
print("벡터 스토어 초기화 시작...")
try:
    vector_store = FAISSVectorStore(VECTOR_DIM)
    if vector_store.index is not None:
        print(f"✅ 임베디드 벡터 검색 엔진이 준비되었습니다. (벡터 수: {vector_store.index.ntotal})")
    else:
        print("⚠️ 벡터 인덱스가 None입니다.")
        vector_store = None
except Exception as e:
    print(f"❌ 벡터 검색 초기화 오류: {e}")
    import traceback
    traceback.print_exc()
    vector_store = None

# 전역 변수로 업데이트 진행 상황 저장
update_progress = {
    "status": "idle",  # idle, running, completed, error
    "progress": 0,     # 0-100
    "message": "",
    "total_steps": 0,
    "current_step": 0
}

# Django DB에서 데이터를 가져와 벡터 DB에 추가하는 함수
def update_vector_db_from_django_sync():
    """Django DB에서 당직 스케줄 데이터를 가져와 임베디드 벡터 DB에 추가 (동기 함수) - 성능 최적화"""
    global update_progress
    
    try:
        # 업데이트 시작
        update_progress["status"] = "running"
        update_progress["progress"] = 0
        update_progress["message"] = "벡터 DB 업데이트 시작..."
        update_progress["current_step"] = 0
        
        print(f"===== 벡터 DB 업데이트 시작 =====")
        
        if vector_store is None:
            print("벡터 DB가 초기화되지 않았습니다. 업데이트를 건너뜁니다.")
            update_progress["status"] = "error"
            update_progress["message"] = "벡터 DB가 초기화되지 않았습니다."
            return {"status": "error", "message": "벡터 DB가 초기화되지 않았습니다. 기능을 사용할 수 없습니다."}
            
        # 현재 년도와 월 기준으로 스케줄 조회
        today = datetime.now().date()
        current_year = today.year
        current_month = today.month
        
        print(f"===== 벡터 DB 업데이트 시작: 현재 날짜 {today} (년도: {current_year}, 월: {current_month}) =====")
        
        # Django 모델에서 현재 년도와 월의 스케줄 데이터만 가져오기
        update_progress["message"] = f"{current_year}년 {current_month}월 스케줄 데이터 조회 중..."
        update_progress["progress"] = 10
        
        schedules = Schedule.objects.filter(
            date__year=current_year,
            date__month=current_month
        ).select_related('doctor', 'doctor__department', 'work_schedule')
        
        print(f"Django DB에서 총 {len(schedules)}개의 스케줄을 가져왔습니다.")
        
        # 데이터가 없으면 경고 메시지 반환
        if len(schedules) == 0:
            print("주의: 스케줄 데이터가 없습니다. 챗봇 응답이 제한될 수 있습니다.")
            update_progress["status"] = "completed"
            update_progress["message"] = "스케줄 데이터가 없습니다. 관리자 페이지에서 일정을 추가해주세요."
            return {"status": "warning", "message": "스케줄 데이터가 없습니다. 관리자 페이지에서 일정을 추가해주세요."}
        
        # 전체 작업 단계 설정
        update_progress["total_steps"] = len(schedules)
        update_progress["message"] = f"총 {len(schedules)}개 스케줄 데이터 처리 중..."
        update_progress["progress"] = 20
        
        # 성능 최적화: 증분 업데이트 - O(1) 스케줄 ID 확인으로 대폭 개선
        existing_schedule_ids = vector_store.schedule_id_index if vector_store.schedule_id_index else set()
        
        # 새로운 스케줄만 필터링 - O(n) 대신 O(1) 검색으로 빠른 처리
        new_schedules = []
        for schedule in schedules:
            if schedule.id not in existing_schedule_ids:
                new_schedules.append(schedule)
        
        if len(new_schedules) == 0:
            print("새로운 스케줄 데이터가 없습니다. 업데이트할 필요가 없습니다.")
            update_progress["status"] = "completed"
            update_progress["progress"] = 100
            update_progress["message"] = "이미 최신 데이터입니다. 업데이트할 필요가 없습니다."
            return {"status": "success", "message": "이미 최신 데이터입니다. 업데이트할 필요가 없습니다."}
        
        print(f"기존 스케줄: {len(existing_schedule_ids)}개, 새로운 스케줄: {len(new_schedules)}개")
        
        # 성능 최적화: 모든 문서를 한 번에 준비
        documents = []
        metadata_list = []
        
        print("문서 데이터 준비 중...")
        for count, schedule in enumerate(new_schedules):
            date_str = schedule.date.strftime('%Y-%m-%d')
            dept_name = schedule.doctor.department.name
            role_name = str(schedule.work_schedule)
            doctor_name = schedule.doctor.name
            phone_number = schedule.doctor.phone_number
            
            # 문서 텍스트 생성 (시간 포맷팅 적용)
            formatted_role = format_work_schedule(role_name)
            document = f"{date_str} {dept_name}의 {formatted_role}는 {doctor_name}입니다. 연락처는 {phone_number}입니다."
            documents.append(document)
            
            # 메타데이터 준비 (role에는 원래 시간 형태 유지 - 시간 비교용)
            metadata_list.append({
                "text": document,
                "date": date_str,
                "department": dept_name,
                "role": role_name,
                "name": doctor_name,
                "phone": phone_number,
                "schedule_id": int(schedule.id)
            })
        
        # 진행 상황 업데이트
        update_progress["progress"] = 40
        update_progress["message"] = "문서 데이터 준비 완료. 임베딩 생성 중..."
        
        # 성능 최적화: 배치로 임베딩 생성 (가장 큰 성능 개선)
        print(f"배치 임베딩 생성 시작... (총 {len(documents)}개 새로운 문서)")
        start_time = time.time()
        
        # 최적화된 배치 크기 사용
        all_embeddings = []
        
        for i in range(0, len(documents), EMBEDDING_BATCH_SIZE):
            batch_docs = documents[i:i+EMBEDDING_BATCH_SIZE]
            
            # GPU 사용 가능 시 더 빠른 처리 - 파라미터 최적화
            batch_embeddings = model.encode(
                batch_docs, 
                convert_to_numpy=True, 
                show_progress_bar=False,
                batch_size=EMBEDDING_BATCH_SIZE,
                normalize_embeddings=True,  # 정규화로 성능 향상
                device='cuda' if torch.cuda.is_available() else 'cpu'
            )
            all_embeddings.extend(batch_embeddings)
            
            # 진행 상황 업데이트 빈도 줄이기 (성능 향상)
            if i % (EMBEDDING_BATCH_SIZE * 3) == 0:  # 3배치마다 한 번씩만 업데이트
                progress = 40 + int((i + len(batch_docs)) / len(documents) * 40)  # 40%~80% 범위
                update_progress["progress"] = progress
                update_progress["message"] = f"임베딩 생성 중... ({i + len(batch_docs)}/{len(documents)})"
            
            batch_num = i//EMBEDDING_BATCH_SIZE + 1
            if i == 0:
                print(f"배치 {batch_num} 완료: {len(batch_docs)}개 문서 처리")
            elif batch_num % 5 == 0:  # 5배치마다 로그 출력
                current_time = time.time() - start_time
                print(f"배치 {batch_num} 완료: {len(batch_docs)}개 문서 처리 ({current_time:.2f}초 경과)")
        
        embedding_time = time.time() - start_time
        print(f"임베딩 생성 완료! 소요시간: {embedding_time:.2f}초")
        print(f"벡터 데이터 {len(all_embeddings)}개를 생성했습니다.")
        
        # 벡터 스토어에 데이터 추가 (증분 업데이트 사용)
        update_progress["message"] = "벡터 DB에 데이터 저장 중..."
        update_progress["progress"] = 85
        
        if all_embeddings:
            # 증분 업데이트로 새로운 벡터만 추가 - 저장은 마지막에 한 번만
            vector_store.add_vectors(all_embeddings, metadata_list, incremental=True, save_immediately=False)
            
            # 최종 저장 (한 번만 수행하여 I/O 최적화)
            update_progress["message"] = "벡터 DB 최종 저장 중..."
            update_progress["progress"] = 95
            vector_store.save_index()
            
            print(f"===== 벡터 DB 업데이트 완료: {len(all_embeddings)}개 추가됨 =====")
            
            # 업데이트 완료
            update_progress["status"] = "completed"
            update_progress["progress"] = 100
            update_progress["message"] = f"업데이트 완료! {len(all_embeddings)}개 새로운 데이터가 추가되었습니다."
            
            return {"status": "success", "message": f"{current_year}년 {current_month}월 데이터 {len(all_embeddings)}개가 벡터 DB에 추가되었습니다."}
        else:
            print("추가할 데이터가 없습니다.")
            update_progress["status"] = "completed"
            update_progress["progress"] = 100
            update_progress["message"] = "추가할 데이터가 없습니다."
            return {"status": "success", "message": f"{current_year}년 {current_month}월에 추가할 데이터가 없습니다."}
            
    except Exception as e:
        import traceback
        print(f"벡터 DB 업데이트 오류: {e}")
        traceback.print_exc()
        
        # 에러 상태 업데이트
        update_progress["status"] = "error"
        update_progress["message"] = f"오류 발생: {str(e)}"
        
        return {"status": "error", "message": f"벡터 DB 업데이트 중 오류 발생: {str(e)}"}

# 비동기 함수로 래핑
update_vector_db_from_django_async = sync_to_async(update_vector_db_from_django_sync)

# 초기 데이터 로드
try:
    # 비동기 컨텍스트에서 호출할 수 없으므로, 초기 데이터 로드는 건너뜁니다.
    # 대신 애플리케이션 시작 후 '/update-vectors' 엔드포인트를 호출하도록 안내합니다.
    print("서버 시작 후 '/update-vectors' 엔드포인트를 호출하여 초기 데이터를 로드하세요.")
except Exception as e:
    print(f"초기 데이터 로드 실패: {e}")

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

# Gemini 모델을 사용한 RAG 요청을 위한 클래스
class RAGRequest(BaseModel):
    query: str
    max_results: int = 10

def parse_date_reference(message: str):
    """사용자 메시지에서 날짜 참조 추출 (오늘, 내일 등)"""
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    day_after_tomorrow = today + timedelta(days=2)  # 모레 (2일 뒤)
    day_after_tomorrow_after_tomorrow = today + timedelta(days=3)  # 글피 (3일 뒤)
    
    # 날짜 묻는 질문 처리
    date_question = re.search(r"(오늘|지금).*(날짜|몇월\s*몇일)", message)
    if date_question:
        return today.strftime('%Y-%m-%d')
    
    # n일 후/뒤 표현 처리 (3일 후, 5일 뒤 등)
    days_later_pattern = re.search(r'(\d+)일\s*(?:후|뒤)', message)
    if days_later_pattern:
        days = int(days_later_pattern.group(1))
        future_date = today + timedelta(days=days)
        print(f"n일 후 표현 감지: {days}일 후 -> {future_date.strftime('%Y-%m-%d')}")
        return future_date.strftime('%Y-%m-%d')
    
    # 다양한 날짜 형식 처리 (ISO 형식, 슬래시, 하이픈 등)
    date_formats = [
        # YYYY-MM-DD 형식 (2025-07-25)
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'full'),
        # MM-DD 형식 (07-25, 7-25)
        (r'(\d{1,2})-(\d{1,2})(?!\d)', 'month_day'),
        # MM/DD 형식 (7/25, 07/25)
        (r'(\d{1,2})/(\d{1,2})(?!\d)', 'month_day'),
        # YYYY/MM/DD 형식 (2025/7/25)
        (r'(\d{4})/(\d{1,2})/(\d{1,2})', 'full_slash'),
    ]
    
    for pattern, format_type in date_formats:
        match = re.search(pattern, message)
        if match:
            try:
                if format_type == 'full':  # YYYY-MM-DD
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                elif format_type == 'full_slash':  # YYYY/MM/DD
                    year = int(match.group(1))
                    month = int(match.group(2)) 
                    day = int(match.group(3))
                elif format_type == 'month_day':  # MM-DD or MM/DD (년도 없음)
                    month = int(match.group(1))
                    day = int(match.group(2))
                    # 현재 년도 사용 (과거든 미래든 상관없이)
                    year = today.year
                
                # 날짜 유효성 검사
                parsed_date = datetime(year, month, day)
                print(f"날짜 형식 '{match.group(0)}' 감지됨 - 날짜 변환: {parsed_date.strftime('%Y-%m-%d')}")
                return parsed_date.strftime('%Y-%m-%d')
                
            except ValueError as e:
                print(f"유효하지 않은 날짜 형식: {match.group(0)} - 오류: {e}")
                continue
    
    # 주차 + 요일 조합 처리 ('이번주 금요일', '다음주 월요일' 등)
    week_patterns = [
        (r"이번\s*주\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)", 0),
        (r"다음\s*주\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)", 1),
        (r"다다음\s*주\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)", 2),
        (r"저번\s*주\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)", -1),
        (r"지난\s*주\s*(월요일|화요일|수요일|목요일|금요일|토요일|일요일)", -1)
    ]
    
    weekday_map = {
        '월요일': 0, '화요일': 1, '수요일': 2, '목요일': 3, 
        '금요일': 4, '토요일': 5, '일요일': 6
    }
    
    for pattern, week_offset in week_patterns:
        match = re.search(pattern, message)
        if match:
            target_weekday = weekday_map[match.group(1)]
            
            # 현재 주의 월요일 찾기
            current_weekday = today.weekday()  # 0=월요일, 6=일요일
            monday_of_current_week = today - timedelta(days=current_weekday)
            
            # 목표 주의 월요일 계산
            target_monday = monday_of_current_week + timedelta(weeks=week_offset)
            
            # 목표 날짜 계산
            target_date = target_monday + timedelta(days=target_weekday)
            
            week_names = {0: '이번주', 1: '다음주', 2: '다다음주', -1: '저번주/지난주'}
            weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
            
            print(f"'{week_names.get(week_offset)} {weekday_names[target_weekday]}' 키워드 감지됨 - 날짜 변환: {target_date.strftime('%Y-%m-%d')}")
            return target_date.strftime('%Y-%m-%d')
    
    # 단순 주차 키워드 처리 ('이번주', '다음주' 등 - 요일 없이)
    simple_week_patterns = [
        (r"이번\s*주", 0),
        (r"다음\s*주", 1), 
        (r"다다음\s*주", 2),
        (r"저번\s*주", -1),
        (r"지난\s*주", -1)
    ]
    
    for pattern, week_offset in simple_week_patterns:
        if re.search(pattern, message):
            # 요일이 명시되지 않은 경우 오늘과 같은 요일로 설정
            current_weekday = today.weekday()
            monday_of_current_week = today - timedelta(days=current_weekday)
            target_monday = monday_of_current_week + timedelta(weeks=week_offset)
            target_date = target_monday + timedelta(days=current_weekday)
            
            week_names = {0: '이번주', 1: '다음주', 2: '다다음주', -1: '저번주/지난주'}
            weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
            
            print(f"'{week_names.get(week_offset)}' 키워드 감지됨 (요일 미지정) - 날짜 변환: {target_date.strftime('%Y-%m-%d')} ({weekday_names[current_weekday]})")
            return target_date.strftime('%Y-%m-%d')
    
    # 단순 요일 처리 ('월요일', '화요일' 등 - 주차 없이)
    weekday_patterns = [
        (r"(?<![가-힣])(월요일)(?![가-힣])", 0),
        (r"(?<![가-힣])(화요일)(?![가-힣])", 1), 
        (r"(?<![가-힣])(수요일)(?![가-힣])", 2),
        (r"(?<![가-힣])(목요일)(?![가-힣])", 3),
        (r"(?<![가-힣])(금요일)(?![가-힣])", 4),
        (r"(?<![가-힣])(토요일)(?![가-힣])", 5),
        (r"(?<![가-힣])(일요일)(?![가-힣])", 6)
    ]
    
    for pattern, target_weekday in weekday_patterns:
        if re.search(pattern, message):
            current_weekday = today.weekday()
            weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
            
            # 이번주 해당 요일 계산 (이번주 우선 - 과거 포함)
            days_ahead = target_weekday - current_weekday
            target_date = today + timedelta(days=days_ahead)
            
            # 며칠 전/후인지 표시
            if days_ahead < 0:
                days_desc = f"{abs(days_ahead)}일 전 (이번주)"
            elif days_ahead == 0:
                days_desc = "오늘"
            else:
                days_desc = f"{days_ahead}일 후 (이번주)"
            
            print(f"'{weekday_names[target_weekday]}' 키워드 감지됨 - 날짜 변환: {target_date.strftime('%Y-%m-%d')} ({days_desc})")
            return target_date.strftime('%Y-%m-%d')
    
    # '어제', '오늘', '내일', '명일', '익일', '모레', '글피' 키워드 처리
    if "어제" in message:
        return yesterday.strftime('%Y-%m-%d')
    elif "글피" in message:
        print(f"'글피' 키워드 감지됨 - 날짜 변환: {day_after_tomorrow_after_tomorrow.strftime('%Y-%m-%d')} (3일 뒤)")
        return day_after_tomorrow_after_tomorrow.strftime('%Y-%m-%d')
    elif "모레" in message:
        print(f"'모레' 키워드 감지됨 - 날짜 변환: {day_after_tomorrow.strftime('%Y-%m-%d')} (2일 뒤)")
        return day_after_tomorrow.strftime('%Y-%m-%d')
    elif any(keyword in message for keyword in ["내일", "명일", "익일"]):
        detected_keyword = next(keyword for keyword in ["내일", "명일", "익일"] if keyword in message)
        print(f"'{detected_keyword}' 키워드 감지됨 - 날짜 변환: {tomorrow.strftime('%Y-%m-%d')}")
        return tomorrow.strftime('%Y-%m-%d')
    elif "오늘" in message:
        return today.strftime('%Y-%m-%d')
    
    # 월 관련 키워드 처리 ('다음달', '저번달', '이번달', '9월' 등)
    month_patterns = [
        (r"다음\s*달", 1),    # 다음달
        (r"저번\s*달", -1),   # 저번달
        (r"지난\s*달", -1),   # 지난달
        (r"이번\s*달", 0),    # 이번달
        (r"(\d{1,2})월", None)  # 특정 월 (9월 등)
    ]
    
    for pattern, month_offset in month_patterns:
        match = re.search(pattern, message)
        if match:
            if month_offset is not None:  # 상대적 월 (다음달, 저번달 등)
                current_month = today.month
                current_year = today.year
                
                target_month = current_month + month_offset
                target_year = current_year
                
                # 월이 범위를 벗어나는 경우 연도 조정
                if target_month > 12:
                    target_month = target_month - 12
                    target_year += 1
                elif target_month < 1:
                    target_month = target_month + 12
                    target_year -= 1
                
                # 해당 월의 첫째 날로 설정 (당직 질문에서는 보통 특정 일자보다는 월 전체를 의미)
                target_date = datetime(target_year, target_month, 1)
                
                month_names = {1: '다음달', -1: '저번달/지난달', 0: '이번달'}
                print(f"'{month_names.get(month_offset)}' 키워드 감지됨 - 날짜 변환: {target_date.strftime('%Y-%m-%d')} ({target_year}년 {target_month}월)")
                return target_date.strftime('%Y-%m-%d')
            else:  # 특정 월 (9월 등)
                month_num = int(match.group(1))
                current_year = today.year
                current_month = today.month
                
                # 현재 월보다 이전 월이면 내년으로, 이후 월이면 올해로 설정
                if month_num < current_month:
                    target_year = current_year + 1
                else:
                    target_year = current_year
                
                try:
                    target_date = datetime(target_year, month_num, 1)
                    print(f"'{month_num}월' 키워드 감지됨 - 날짜 변환: {target_date.strftime('%Y-%m-%d')} ({target_year}년 {month_num}월)")
                    return target_date.strftime('%Y-%m-%d')
                except ValueError:
                    print(f"유효하지 않은 월: {month_num}")
                    continue
    
    # '2025년 6월 15일' 형식 처리 (한글 연도 포함)
    year_date_pattern = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', message)
    if year_date_pattern:
        year = int(year_date_pattern.group(1))
        month = int(year_date_pattern.group(2))
        day = int(year_date_pattern.group(3))
        try:
            parsed_date = datetime(year, month, day)
            print(f"연도 포함 한글 날짜 형식 감지됨 - 날짜 변환: {parsed_date.strftime('%Y-%m-%d')}")
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            # 유효하지 않은 날짜 처리
            return None
    
    # '5월 10일', '10일' 형식 처리 (한글 형식 - 연도 없음)
    date_pattern = re.search(r'(\d{1,2})월\s*(\d{1,2})일', message)
    if date_pattern:
        month = int(date_pattern.group(1))
        day = int(date_pattern.group(2))
        # 기본적으로 현재 년도 사용 (과거든 미래든 상관없이)
        year = today.year
        try:
            parsed_date = datetime(year, month, day)
            print(f"한글 날짜 형식 감지됨 - 날짜 변환: {parsed_date.strftime('%Y-%m-%d')}")
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            # 유효하지 않은 날짜 처리
            return None
    
    # 단순히 '9일'처럼 일만 명시된 경우 (한글 형식)
    day_pattern = re.search(r'(\d{1,2})일', message)
    if day_pattern:
        day = int(day_pattern.group(1))
        # 같은 달로 가정
        month = today.month
        year = today.year
        
        try:
            # 먼저 현재 월의 날짜로 시도
            parsed_date = datetime(year, month, day)
            print(f"일자만 있는 날짜 변환 (현재 월): {parsed_date.strftime('%Y-%m-%d')}")
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            # 현재 월에 해당 날짜가 없으면 다음 달로 시도
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1
            try:
                parsed_date = datetime(year, month, day)
                print(f"일자만 있는 날짜 변환 (다음 월): {parsed_date.strftime('%Y-%m-%d')}")
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                # 유효하지 않은 날짜 처리
                return None
    
    # 시간 파싱 (예: 내일 10시에)
    m = re.search(r"(오늘|내일)? ?(\d{1,2})시", message)
    if m:
        hour = int(m.group(2))
        base = today if (m.group(1) == "오늘" or not m.group(1)) else tomorrow
        dt = base.replace(hour=hour, minute=0, second=0, microsecond=0)
        return dt.strftime('%Y-%m-%d')
    
    return None

# 새로운 함수: Gemini 모델을 사용한 질문 응답
async def generate_gemini_response(query: str, context: str):
    """Gemini 모델을 사용해 질문에 답변 생성"""
    try:
        # Gemini 모델 설정
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # 현재 날짜와 내일 날짜를 문자열로 변환
        today_date = datetime.now().strftime('%Y-%m-%d')
        tomorrow_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        current_hour = datetime.now().hour
        
        # 프롬프트 생성
        prompt = f"""
다음 정보를 바탕으로 사용자의 질문에 답변해주세요.
정보:
{context}

질문: {query}

답변을 할 때 다음 사항을 지켜주세요:
1. 정보에 있는 내용만 사용하여 답변하세요.
2. '지금'이나 '현재'라는 단어가 나오면, 현재 시간({current_hour}시)에 해당하는 당직의를 반드시 찾아서 답변하세요.
3. 현재 날짜({today_date})와 현재 시간({current_hour}시)에 모두 일치하는 당직 정보를 우선적으로 제공하세요.
4. 현재 시간에 해당하는 당직의가 없으면, "현재 시간({current_hour}시)에는 당직의가 없습니다."라고 답변하세요.
5. 간결하고 명확하게 답변하세요.
6. 한국어로 답변하세요.
"""
        
        # 응답 생성
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini 응답 생성 오류: {e}")
        return f"죄송합니다. 응답을 생성하는 중 오류가 발생했습니다: {str(e)}"

# 새로운 엔드포인트: RAG 기반 질의응답
@app.post("/rag")
async def rag_query(req: RAGRequest):
    """RAG 기반 질의응답 엔드포인트"""
    print("🔍🔍🔍 RAG 엔드포인트 호출됨! 🔍🔍🔍")
    print(f"RAG 요청 쿼리: {req.query}")
    try:
        if vector_store is None:
            return {"status": "error", "message": "벡터 DB가 초기화되지 않았습니다."}
        
        query = req.query
        max_results = req.max_results
        
        # 쿼리에서 날짜 추출
        date_reference = parse_date_reference(query)
        tomorrow_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        # 현재 시간 정보 추출
        current_hour = datetime.now().hour
        
        # 쿼리 증강: 현재 시간 정보 추가
        if "지금" in query or "현재" in query:
            augmented_query = f"{query} (현재 날짜: {today_date}, 현재 시간: {current_hour}시)"
            print(f"쿼리 증강: '{query}' -> '{augmented_query}'")
        else:
            augmented_query = query
        
        # 쿼리 임베딩 생성 (증강된 쿼리 사용)
        query_embedding = model.encode(augmented_query)
        
        # 벡터 검색 수행 (더 많은 결과 가져오기)
        all_results = vector_store.search(query_embedding, k=50)
        
        if not all_results:
            return {
                "status": "warning",
                "message": "관련 정보를 찾을 수 없습니다.",
                "answer": "죄송합니다. 해당 질문에 대한 정보를 찾을 수 없습니다."
            }
        
        # 현재 날짜로 먼저 필터링
        today_results = [r for r in all_results if r["entity"]["date"] == today_date]
        print(f"현재 날짜({today_date})에 해당하는 결과: {len(today_results)}개")
        
        if today_results:
            all_results = today_results
            print("현재 날짜의 결과만 사용합니다.")
        
        # 부서 정보 추출
        department = None
        for r in all_results:
            if "department" in r["entity"]:
                # 부서명이 쿼리에 포함되어 있는지 확인
                dept_name = r["entity"]["department"]
                if dept_name in query:
                    department = dept_name
                    print(f"쿼리에서 부서 추출: {department}")
                    break
        
        # 현재 날짜와 시간에 해당하는 결과만 필터링
        if "지금" in query or "현재" in query:
            filtered_results = []
            print(f"현재 날짜({today_date})와 시간({current_hour}시)에 해당하는 결과 필터링")
            
            # Django DB에서 직접 조회
            try:
                print(f"Django DB 직접 검색: 날짜={today_date}, 부서={department}, 시간={current_hour}시")
                schedule_result = await get_schedule_from_db_async(today_date, department, None, None, False, current_hour)
                
                if schedule_result:
                    if isinstance(schedule_result, list):
                        schedule = schedule_result[0]
                    else:
                        schedule = schedule_result
                        
                    print(f"DB 직접 조회 성공: {schedule.date} - {schedule.doctor.name}, 시간={schedule.work_schedule}")
                    
                    # 결과를 벡터 검색 결과 형식으로 변환
                    result = {
                        "entity": {
                            "text": f"{schedule.date} {schedule.doctor.department.name}의 {schedule.work_schedule}는 {schedule.doctor.name}입니다. 연락처는 {schedule.doctor.phone_number}입니다.",
                            "date": str(schedule.date),
                            "department": schedule.doctor.department.name,
                            "role": str(schedule.work_schedule),
                            "name": schedule.doctor.name,
                            "phone": schedule.doctor.phone_number,
                            "schedule_id": schedule.id
                        },
                        "distance": 1.0
                    }
                    filtered_results.append(result)
                    print(f"현재 시간에 해당하는 결과 찾음: {schedule.date} - {schedule.doctor.department.name} - {schedule.work_schedule}")
                else:
                    print(f"DB 직접 조회 실패: {today_date}, {department}에 해당하는 스케줄이 없습니다.")
            except Exception as e:
                print(f"DB 직접 조회 오류: {e}")
                import traceback
                traceback.print_exc()
            
            if filtered_results:
                all_results = filtered_results
                print(f"현재 날짜와 시간에 해당하는 결과로 필터링: {len(filtered_results)}개")
            else:
                print("현재 날짜와 시간에 해당하는 결과가 없습니다.")
                all_results = []
        
        # 시간대에 따른 결과 필터링
        time_filtered_results = []
        if "지금" in query or "현재" in query:
            print(f"현재 시간({current_hour}시)에 해당하는 결과 필터링")
            for result in all_results:
                # 현재 날짜와 일치하는지 먼저 확인
                if result["entity"]["date"] != today_date:
                    continue
                    
                role = result["entity"]["role"]
                times = role.split(' - ')
                if len(times) == 2:
                    try:
                        start_hour = int(times[0].split(':')[0])
                        end_hour = int(times[1].split(':')[0])
                        
                        # 24시간 당직인 경우 (08:00 - 08:00)
                        is_24h_shift = start_hour == end_hour
                        
                        # 시작 시간이 종료 시간보다 크면 익일로 처리
                        if end_hour <= start_hour and not is_24h_shift:
                            end_hour += 24
                        
                        # 현재 시간이 범위 내에 있는지 확인
                        current_hour_normalized = current_hour
                        if current_hour < 12 and start_hour > 12:
                            current_hour_normalized = current_hour + 24
                            
                        # 24시간 당직이거나 현재 시간이 범위 내에 있는 경우
                        if is_24h_shift or (start_hour <= current_hour_normalized < end_hour):
                            # 부서 필터링 추가
                            if department is None or result["entity"]["department"] == department:
                                time_filtered_results.append(result)
                                print(f"현재 시간에 해당하는 결과 찾음: {result['entity']['date']} - {result['entity']['department']} - {role}")
                    except Exception as e:
                        print(f"시간 파싱 오류: {e}")
                        continue
        
        # 결과 필터링 (날짜 기준)
        filtered_results = all_results  # 기본값으로 모든 결과 사용
        
        # 시간 필터링 결과가 있으면 우선 사용
        if time_filtered_results:
            print(f"시간 필터링 결과: {len(time_filtered_results)}개")
            
            # 부서 필터링 추가
            if department:
                dept_time_filtered = [r for r in time_filtered_results if r["entity"]["department"] == department]
                if dept_time_filtered:
                    print(f"부서({department})와 시간이 모두 일치하는 결과: {len(dept_time_filtered)}개")
                    time_filtered_results = dept_time_filtered
            
            # 현재 날짜와 일치하는 결과 우선
            today_matches = [r for r in time_filtered_results if r["entity"]["date"] == today_date]
            if today_matches:
                print(f"오늘 날짜({today_date})와 시간이 모두 일치하는 결과: {len(today_matches)}개")
                filtered_results = today_matches
            else:
                # 오늘 날짜가 없으면 시간 필터링된 결과 사용
                filtered_results = time_filtered_results
                
        # 특정 날짜가 지정된 경우
        elif date_reference:
            date_filtered_results = [r for r in all_results if r["entity"]["date"] == date_reference]
            
            if date_filtered_results:
                print(f"날짜 '{date_reference}'에 일치하는 결과 {len(date_filtered_results)}개 찾음")
                # 부서 필터링 추가
                if department:
                    dept_date_filtered = [r for r in date_filtered_results if r["entity"]["department"] == department]
                    if dept_date_filtered:
                        filtered_results = dept_date_filtered
                        print(f"날짜와 부서가 모두 일치하는 결과: {len(dept_date_filtered)}개")
                    else:
                        filtered_results = date_filtered_results
                else:
                    filtered_results = date_filtered_results
            else:
                print(f"날짜 '{date_reference}'에 일치하는 결과가 없습니다.")
                # 필터링 없이 진행
        
        # 글피 키워드 있지만 날짜 필터링 결과가 없는 경우 (3일 뒤)
        if "글피" in query and not date_reference:
            day_after_tomorrow_after_tomorrow_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
            glpi_results = [r for r in all_results if r["entity"]["date"] == day_after_tomorrow_after_tomorrow_date]
            
            if glpi_results:
                print(f"'글피' 키워드를 위한 특별 처리: 3일 뒤({day_after_tomorrow_after_tomorrow_date})에 해당하는 결과 {len(glpi_results)}개 찾음")
                # 부서 필터링 추가
                if department:
                    dept_glpi_filtered = [r for r in glpi_results if r["entity"]["department"] == department]
                    if dept_glpi_filtered:
                        filtered_results = dept_glpi_filtered
                        print(f"3일 뒤 날짜와 부서가 모두 일치하는 결과: {len(dept_glpi_filtered)}개")
                    else:
                        filtered_results = glpi_results
                else:
                    filtered_results = glpi_results
        
        # 모레 키워드 있지만 날짜 필터링 결과가 없는 경우 (2일 뒤)
        elif "모레" in query and not date_reference:
            day_after_tomorrow_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
            more_results = [r for r in all_results if r["entity"]["date"] == day_after_tomorrow_date]
            
            if more_results:
                print(f"'모레' 키워드를 위한 특별 처리: 2일 뒤({day_after_tomorrow_date})에 해당하는 결과 {len(more_results)}개 찾음")
                # 부서 필터링 추가
                if department:
                    dept_more_filtered = [r for r in more_results if r["entity"]["department"] == department]
                    if dept_more_filtered:
                        filtered_results = dept_more_filtered
                        print(f"2일 뒤 날짜와 부서가 모두 일치하는 결과: {len(dept_more_filtered)}개")
                    else:
                        filtered_results = more_results
                else:
                    filtered_results = more_results
        
        # 내일 관련 키워드 있지만 날짜 필터링 결과가 없는 경우
        elif any(keyword in query for keyword in ["내일", "명일", "익일"]) and not date_reference:
            tomorrow_results = [r for r in all_results if r["entity"]["date"] == tomorrow_date]
            
            if tomorrow_results:
                detected_tomorrow_keyword = next(keyword for keyword in ["내일", "명일", "익일"] if keyword in query)
                print(f"'{detected_tomorrow_keyword}' 키워드를 위한 특별 처리: 내일({tomorrow_date})에 해당하는 결과 {len(tomorrow_results)}개 찾음")
                # 부서 필터링 추가
                if department:
                    dept_tomorrow_filtered = [r for r in tomorrow_results if r["entity"]["department"] == department]
                    if dept_tomorrow_filtered:
                        filtered_results = dept_tomorrow_filtered
                        print(f"내일 날짜와 부서가 모두 일치하는 결과: {len(dept_tomorrow_filtered)}개")
                    else:
                        filtered_results = tomorrow_results
                else:
                    filtered_results = tomorrow_results
        
        # 부서 필터링 (다른 필터가 적용되지 않은 경우)
        if department and filtered_results == all_results:
            dept_filtered = [r for r in all_results if r["entity"]["department"] == department]
            if dept_filtered:
                print(f"부서({department})로 필터링된 결과: {len(dept_filtered)}개")
                filtered_results = dept_filtered
        
        # 상위 결과만 유지
        results = filtered_results[:max_results]
        
        # 검색된 문서 출력 (로그)
        print(f"'{query}' 관련 검색 결과:")
        for i, result in enumerate(results):
            print(f"  {i+1}. 유사도: {result['distance']:.4f}, 내용: {result['entity']['text']}")
        
        # 컨텍스트 생성
        context = "\n".join([r['entity']['text'] for r in results])
        
        # 시간 정보 명시적 전달
        time_context = f"현재 날짜는 {today_date}이고, 현재 시간은 {current_hour}시입니다."
        
        # Gemini로 응답 생성 (시간 정보 포함)
        answer = await generate_gemini_response(query, context + "\n" + time_context)
        
        return {
            "status": "success",
            "answer": answer,
            "sources": results
        }
        
    except Exception as e:
        import traceback
        print(f"RAG 질의응답 오류: {e}")
        traceback.print_exc()
        return {"status": "error", "message": f"오류 발생: {str(e)}"}

# 루트 경로 - 메인 챗봇 인터페이스
@app.get("/", response_class=HTMLResponse)
async def get_chatbot_interface():
    """메인 챗봇 웹 인터페이스"""
    html_file = static_dir / "index.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return """
        <html>
            <head>
                <title>당직 스케줄 챗봇</title>
            </head>
            <body>
                <h1>당직 스케줄 챗봇</h1>
                <p>인터페이스를 불러올 수 없습니다.</p>
                <p><a href="/static/index.html">직접 링크</a></p>
            </body>
        </html>
        """

# Gemini RAG 웹 인터페이스
@app.get("/gemini-rag", response_class=HTMLResponse)
async def get_gemini_rag():
    """Gemini RAG 웹 인터페이스"""
    html_file = static_dir / "gemini_rag.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return """
        <html>
            <head>
                <title>Gemini RAG 챗봇</title>
            </head>
            <body>
                <h1>Gemini RAG 챗봇</h1>
                <p>인터페이스를 불러올 수 없습니다.</p>
            </body>
        </html>
        """

# Django ORM을 사용하는 동기 함수들을 정의
def get_schedule_from_db(date_str, dept_name, role_name=None, time_range=None, night_shift=False, specific_hour=None):
    """Django DB에서 스케줄 정보를 가져오는 동기 함수"""
    
    print(f"===== get_schedule_from_db 시작 =====")
    print(f"     date_str: '{date_str}'")
    print(f"     dept_name: '{dept_name}'")
    print(f"     role_name: '{role_name}'")
    print(f"     time_range: '{time_range}'")
    print(f"     night_shift: {night_shift}")
    print(f"     specific_hour: {specific_hour}")
    
    try:
        # 쿼리 기본 설정
        print(f"===== Django ORM 쿼리 구성 중 =====")
        query = Schedule.objects.filter(
            date=date_str,
            doctor__department__name=dept_name
        ).select_related('doctor', 'work_schedule')
        
        print(f"조회 기준: 날짜={date_str}, 부서={dept_name}, 역할={role_name}, 시간대={time_range}, 특정시간={specific_hour}")
        
        # 특정 시간이 새벽 시간대(0-8시)인 경우, 전날 당직도 함께 검색
        if specific_hour is not None and 0 <= specific_hour < 8:
            # 전날 날짜 계산
            previous_date = (datetime.strptime(date_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"새벽 시간대({specific_hour}시)이므로 전날({previous_date})의 당직도 검색합니다")
            
            # 전날 쿼리도 추가
            previous_day_query = Schedule.objects.filter(
                date=previous_date,
                doctor__department__name=dept_name
            ).select_related('doctor', 'work_schedule')
            
            # 전날 및 당일 스케줄 모두 가져오기
            all_schedules = list(previous_day_query.all()) + list(query.all())
        else:
            # 스케줄 목록 가져오기
            print(f"===== Django ORM 쿼리 실행 중 =====")
            all_schedules = list(query.all())
            print(f"===== Django ORM 쿼리 실행 완료 - 결과 {len(all_schedules)}개 =====")
        
        if not all_schedules:
            print(f"해당 날짜/부서에 스케줄이 없습니다: {date_str}, {dept_name}")
            return None
        
        # 디버깅: 모든 스케줄 출력
        for i, schedule in enumerate(all_schedules):
            print(f"  스케줄 {i+1}: {schedule.work_schedule}, {schedule.doctor.name}, 날짜={schedule.date}")
        
        # 시간이 특정되지 않고 역할도 지정되지 않은 경우 모든 스케줄 반환
        if specific_hour is None and role_name is None and time_range is None:
            print("시간이나 역할이 특정되지 않아 모든 스케줄을 반환합니다.")
            return all_schedules
        
        # 특정 시간이 지정된 경우 (가장 우선)
        if specific_hour is not None:
            matching_schedules = []
            overnight_schedules = []  # 야간 근무(익일 새벽까지) 스케줄
            
            for schedule in all_schedules:
                try:
                    # work_schedule 문자열에서 시간 추출 (예: "08:30 - 17:30")
                    times = str(schedule.work_schedule).split(' - ')
                    if len(times) == 2:
                        # 시작 시간을 분 단위로 변환 (예: "08:30" → 8*60+30 = 510분)
                        start_parts = times[0].split(':')
                        start_hour = int(start_parts[0])
                        start_minute = int(start_parts[1]) if len(start_parts) > 1 else 0
                        start_total_minutes = start_hour * 60 + start_minute
                        
                        # 종료 시간을 분 단위로 변환 (예: "17:30" → 17*60+30 = 1050분)
                        end_parts = times[1].split(':')
                        end_hour = int(end_parts[0])
                        end_minute = int(end_parts[1]) if len(end_parts) > 1 else 0
                        end_total_minutes = end_hour * 60 + end_minute
                        
                        # 현재 시간을 분 단위로 변환 (예: 17시 → 17*60 = 1020분)
                        specific_total_minutes = specific_hour * 60
                        
                        # 시작 시간이 종료 시간과 같거나 더 클 경우 익일로 처리
                        if end_total_minutes <= start_total_minutes:
                            # 새벽 시간대(0-8시)에 대한 질의인 경우, 전날의 당직을 찾습니다
                            if 0 <= specific_hour < 8:
                                # 전날이면서 야간 근무인 경우에만 저장
                                schedule_date = schedule.date.strftime('%Y-%m-%d')
                                query_date = datetime.strptime(date_str, '%Y-%m-%d')
                                schedule_datetime = datetime.strptime(schedule_date, '%Y-%m-%d')
                                
                                # 전날 스케줄이면서 야간 근무인 경우
                                if schedule_datetime.date() < query_date.date() and end_total_minutes <= start_total_minutes:
                                    overnight_schedules.append(schedule)
                                    print(f"    ✓ 전날 야간 근무 일치: {schedule.work_schedule}, {schedule.date}")
                            
                            end_total_minutes += 24 * 60  # 24시간을 분으로 변환해서 더함
                        
                        print(f"    시간 비교: {start_total_minutes}분({start_hour}:{start_minute:02d}) <= {specific_total_minutes}분({specific_hour}:00) < {end_total_minutes}분({end_hour}:{end_minute:02d})")
                        
                        # 특정 시간이 시작 시간과 종료 시간 사이에 있는지 확인
                        # specific_hour가 24 이상인 경우(익일 새벽)도 처리
                        specific_total_minutes_normalized = specific_total_minutes
                        if specific_hour < 12 and start_hour > 12:
                            specific_total_minutes_normalized = specific_total_minutes + 24 * 60
                            
                        if start_total_minutes <= specific_total_minutes_normalized < end_total_minutes:
                            matching_schedules.append(schedule)
                            print(f"    ✓ 시간 일치: {schedule.work_schedule}, {schedule.date}")
                except Exception as e:
                    print(f"    시간 파싱 오류: {e}")
                    continue
            
            # 새벽 시간대(0-8시)에 대한 질의일 경우 전날 당직을 우선 반환
            if 0 <= specific_hour < 8 and overnight_schedules:
                print(f"    새벽 시간대({specific_hour}시)에 대한 질의로 전날 당직을 우선 반환합니다.")
                return overnight_schedules[0]
            
            if matching_schedules:
                return matching_schedules[0]
        
        # 모든 조건에 맞지 않으면, 모든 스케줄 반환 (후속 질문에서 많이 사용)
        print("조건에 맞는 특정 스케줄을 찾지 못해 모든 스케줄을 반환합니다.")
        return all_schedules
    
    except Exception as e:
        print(f"===== get_schedule_from_db 오류 발생 =====")
        print(f"     오류 타입: {type(e).__name__}")
        print(f"     오류 메시지: {str(e)}")
        import traceback
        print(f"     스택 트레이스:")
        traceback.print_exc()
        
        # 부서명 관련 오류인지 확인
        if "department" in str(e).lower():
            print(f"     부서명 관련 오류 의심: '{dept_name}'")
            
        # 날짜 관련 오류인지 확인  
        if "date" in str(e).lower() or "datetime" in str(e).lower():
            print(f"     날짜 관련 오류 의심: '{date_str}'")
            
        raise e  # 오류를 다시 발생시켜서 상위에서 처리하도록 함

# 동기 함수를 비동기로 변환
get_schedule_from_db_async = sync_to_async(get_schedule_from_db)

@app.get("/update-vectors")
async def update_vectors():
    """벡터 DB를 Django DB의 최신 데이터로 업데이트"""
    global update_progress
    
    if vector_store is None:
        return {"status": "error", "message": "벡터 DB가 초기화되지 않았습니다. 기능을 사용할 수 없습니다."}
    
    # 이미 업데이트가 진행 중이면 거부
    if update_progress["status"] == "running":
        return {"status": "error", "message": "이미 업데이트가 진행 중입니다."}
    
    # 백그라운드에서 업데이트 실행
    asyncio.create_task(update_vector_db_from_django_async())
    
    # 즉시 응답 반환
    return {"status": "started", "message": "벡터 DB 업데이트가 시작되었습니다."}

@app.get("/update-progress")
async def get_update_progress():
    """벡터 DB 업데이트 진행 상황 조회"""
    return update_progress

@app.get("/departments")
async def get_departments():
    """DB에서 부서 목록 조회"""
    try:
        departments = await get_all_departments_async()
        return {
            "status": "success",
            "departments": departments
        }
    except Exception as e:
        print(f"부서 목록 조회 오류: {e}")
        return {
            "status": "error",
            "message": f"부서 목록을 가져오는 중 오류가 발생했습니다: {str(e)}",
            "departments": []
        }

@app.get("/vector-info")
async def get_vector_info():
    """저장된 벡터 정보 조회"""
    try:
        if vector_store is None:
            return {
                "status": "error",
                "message": "벡터 DB가 초기화되지 않았습니다.",
                "total_vectors": 0,
                "departments": [],
                "date_range": {},
                "schedule_ids": []
            }
        
        total_vectors = vector_store.index.ntotal if vector_store.index else 0
        total_metadata = len(vector_store.metadata)
        total_schedule_ids = len(vector_store.schedule_id_index)
        
        # 부서별 통계
        departments = {}
        dates = []
        roles = {}
        
        for item in vector_store.metadata:
            # 부서별 카운트
            dept = item.get('department', 'Unknown')
            departments[dept] = departments.get(dept, 0) + 1
            
            # 날짜 수집
            date = item.get('date')
            if date:
                dates.append(date)
            
            # 역할별 카운트
            role = item.get('role', 'Unknown')
            roles[role] = roles.get(role, 0) + 1
        
        # 날짜 범위 계산
        date_range = {}
        if dates:
            dates.sort()
            date_range = {
                "earliest": dates[0],
                "latest": dates[-1],
                "total_days": len(set(dates))
            }
        
        # 최근 추가된 스케줄 (상위 10개)
        recent_schedules = []
        for item in vector_store.metadata[-10:]:  # 마지막 10개
            recent_schedules.append({
                "date": item.get('date'),
                "department": item.get('department'),
                "role": item.get('role'),
                "name": item.get('name'),
                "schedule_id": item.get('schedule_id')
            })
        
        return {
            "status": "success",
            "total_vectors": total_vectors,
            "total_metadata": total_metadata,
            "total_schedule_ids": total_schedule_ids,
            "departments": departments,
            "date_range": date_range,
            "roles": roles,
            "recent_schedules": recent_schedules,
            "vector_dim": vector_store.vector_dim if vector_store else 0
        }
        
    except Exception as e:
        print(f"벡터 정보 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"벡터 정보 조회 중 오류 발생: {str(e)}",
            "total_vectors": 0,
            "departments": [],
            "date_range": {},
            "schedule_ids": []
        }

@app.delete("/vector-db")
async def delete_vector_db():
    """벡터 DB 완전 삭제"""
    try:
        global vector_store
        
        if vector_store is None:
            return {
                "status": "error",
                "message": "벡터 DB가 초기화되지 않았습니다."
            }
        
        # 벡터 DB 메모리에서 초기화
        vector_store.index = faiss.IndexFlatIP(vector_store.vector_dim)
        vector_store.metadata = []
        vector_store.schedule_id_index = set()
        
        # 파일 삭제
        import os
        if os.path.exists(VECTOR_DB_PATH):
            os.remove(VECTOR_DB_PATH)
            print(f"벡터 DB 파일 삭제됨: {VECTOR_DB_PATH}")
        
        # 압축 파일도 삭제 (있는 경우)
        compressed_path = VECTOR_DB_PATH + ".gz"
        if os.path.exists(compressed_path):
            os.remove(compressed_path)
            print(f"압축 벡터 DB 파일 삭제됨: {compressed_path}")
        
        # 업데이트 진행 상황 초기화
        global update_progress
        update_progress = {
            "status": "idle",
            "progress": 0,
            "message": "",
            "total_steps": 0,
            "current_step": 0
        }
        
        print("벡터 DB가 완전히 초기화되었습니다.")
        
        return {
            "status": "success",
            "message": "벡터 DB가 성공적으로 삭제되었습니다. 다시 사용하려면 '벡터 DB 업데이트' 버튼을 클릭하세요."
        }
        
    except Exception as e:
        print(f"벡터 DB 삭제 오류: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"벡터 DB 삭제 중 오류 발생: {str(e)}"
        }

@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    print("🚀🚀🚀 CHAT 엔드포인트 호출됨! 🚀🚀🚀")
    print(f"요청 메시지: {req.message}")
    start_time = time.time()  # 응답 시간 측정 시간
    
    # 세션 ID 처리 개선 - 요청 body와 헤더 모두에서 확인
    session_id = None
    
    # 1. 요청 body에서 session_id 확인
    if hasattr(req, 'session_id') and req.session_id:
        session_id = req.session_id
        print(f"📋 Body에서 session_id 획득: {session_id}")
    
    # 2. 헤더에서 X-Session-ID 확인
    if not session_id:
        header_session_id = request.headers.get('X-Session-ID')
        if header_session_id:
            session_id = header_session_id
            print(f"📋 Header에서 session_id 획득: {session_id}")
    
    # 3. 둘 다 없으면 새로 생성
    if not session_id:
        session_id = str(uuid.uuid4())
        print(f"📋 새로운 session_id 생성: {session_id}")
    
    client_ip = request.client.host if request.client else "unknown"
    
    print(f"===== SESSION ID 처리 =====")
    print(f"     요청에서 받은 session_id: {getattr(req, 'session_id', None)}")
    print(f"     헤더의 X-Session-ID: {request.headers.get('X-Session-ID', 'None')}")
    print(f"     최종 사용할 session_id: {session_id}")
    
    # 세션별 대화 맥락 가져오기
    context = get_or_create_session_context(session_id)
    print(f"===== SESSION CONTEXT 상태 =====")
    print(f"     전체 세션 수: {len(session_conversations)}")
    print(f"     현재 세션의 대화 기록 수: {len(context.conversation_history)}")
    
    try:
        message = req.message
        
        current_datetime = datetime.now()
        print(f"\n===== 새 채팅 요청: '{message}' =====")
        print(f"===== 현재 시간: {current_datetime} =====")
        print(f"===== 현재 날짜: {current_datetime.strftime('%Y-%m-%d')} =====")
        print(f"===== 세션 ID: {session_id} =====")
        print(f"===== 이전 맥락: {context.get_context_info()} =====")
        
        # 후속 질문인지 확인
        is_followup = is_follow_up_question(message)
        print(f"===== 후속 질문 여부: {is_followup} =====")
        print(f"===== 후속 질문 패턴 상세 체크 =====")
        print(f"     원본 메시지: '{message}'")
        print(f"     정리된 메시지: '{message.strip()}'")
        print(f"     '내일은?' 패턴 매치: {bool(re.search(r'^내일은\?*$', message.strip(), re.IGNORECASE))}")
        
        # 후속 질문 처리 - 강화된 버전
        if is_followup:
            print("===== 후속 질문으로 감지됨 =====")
            print(f"===== 이전 맥락 상세 정보 =====")
            print(f"     last_department: '{context.last_department}'")
            print(f"     last_role: '{context.last_role}'")
            print(f"     last_date: '{context.last_date}'")
            print(f"     last_doctor: '{context.last_doctor}'")
            print(f"     last_doctors: {context.last_doctors}")
            print(f"     last_query: '{context.last_query}'")
            
            if context.last_department:
                print("===== 후속 질문 처리 시작 =====")
                time_ref = extract_follow_up_reference(message)
                print(f"===== 추출된 시간 참조: '{time_ref}' =====")
                
                if time_ref:
                    # 시간 참조로부터 실제 날짜 계산
                    target_date = calculate_from_follow_up_reference(time_ref)
                    print(f"===== 계산된 목표 날짜: '{target_date}' =====")
                    
                    if target_date:
                        print(f"===== 계산된 목표 결과: '{target_date}' =====")
                        
                        # 연락처 요청 처리
                        if target_date == 'contact_request':
                            print("===== 연락처 후속 질문 처리 =====")
                            
                            # 가장 최근의 의사만 확인 (연락처 후속 질문에서는 최근 의사만 참조)
                            doctors_to_check = []
                            if context.last_doctor:
                                doctors_to_check = [context.last_doctor]
                                print(f"     이전 맥락에서 가장 최근 의사: {context.last_doctor}")
                            elif context.last_doctors and len(context.last_doctors) > 0:
                                # last_doctor가 없으면 last_doctors의 첫 번째 의사 사용
                                doctors_to_check = [context.last_doctors[0]]
                                print(f"     이전 맥락에서 첫 번째 의사 사용: {context.last_doctors[0]}")
                            
                            if doctors_to_check:
                                contact_responses = []
                                
                                for doctor_name in doctors_to_check:
                                    print(f"     {doctor_name} 의사 정보 조회 중...")
                                    doctor_info = await get_doctor_info_async(doctor_name)
                                    
                                    if doctor_info and doctor_info.phone_number:
                                        contact_responses.append(f"• {doctor_name}: {doctor_info.phone_number}")
                                        print(f"     ✅ {doctor_name} 연락처: {doctor_info.phone_number}")
                                    elif doctor_info:
                                        contact_responses.append(f"• {doctor_name}: 연락처 정보 없음")
                                        print(f"     ⚠️ {doctor_name} 연락처 정보 없음")
                                    else:
                                        contact_responses.append(f"• {doctor_name}: 정보를 찾을 수 없음")
                                        print(f"     ❌ {doctor_name} 정보 없음")
                                
                                if contact_responses:
                                    # 이제 항상 한 명의 의사만 처리하므로 단순한 형태로 응답
                                    doctor_name = doctors_to_check[0]
                                    contact_info = contact_responses[0].split(': ')[1]
                                    if contact_info == "정보를 찾을 수 없음":
                                        response_text = f"죄송합니다. {doctor_name} 의사의 정보를 찾을 수 없습니다."
                                    elif contact_info == "연락처 정보 없음":
                                        response_text = f"{doctor_name} 의사의 연락처 정보가 등록되어 있지 않습니다."
                                    else:
                                        response_text = f"{doctor_name} 의사의 연락처는 {contact_info}입니다."
                                    
                                    print(f"===== 연락처 정보 응답: {response_text} =====")
                                else:
                                    response_text = "죄송합니다. 연락처 정보를 찾을 수 없습니다."
                                
                                entities = {'doctor_name': doctors_to_check[0], 'contact_request': True}
                                context.update_context(entities, message, response_text)
                                
                                response_time = (time.time() - start_time) * 1000
                                return create_chatbot_response_with_logging(
                                    response_text=response_text,
                                    session_id=session_id,
                                    message=message,
                                    response_time=response_time,
                                    client_ip=client_ip,
                                    entities=entities
                                )
                            else:
                                response_text = "죄송합니다. 이전 대화에서 언급된 의사가 없습니다. '의사이름 연락처 알려줘' 형태로 질문해 주세요."
                                response_time = (time.time() - start_time) * 1000
                                return create_chatbot_response_with_logging(
                                    response_text=response_text,
                                    session_id=session_id,
                                    message=message,
                                    response_time=response_time,
                                    client_ip=client_ip,
                                    entities={'contact_request_failed': True}
                                )
                        
                        # 내일모레와 같은 다중 날짜 처리
                        elif target_date.startswith("multiple_dates:"):
                            dates_str = target_date.split(":", 1)[1]
                            dates = dates_str.split(",")
                            print(f"===== 다중 날짜 처리: {dates} =====")
                            
                            responses = []
                            for date in dates:
                                print(f"===== {date} 날짜에 대한 DB 조회 시작 =====")
                                
                                schedules = await get_schedule_from_db_async(
                                    date, context.last_department, None, None, False, None
                                )
                                
                                if schedules:
                                    if isinstance(schedules, list):
                                        if len(schedules) == 1:
                                            single_schedule = schedules[0]
                                            phone_info = f" (연락처: {single_schedule.doctor.phone_number})" if single_schedule.doctor.phone_number else ""
                                            response_part = f"[{date}] {context.last_department} {single_schedule.work_schedule}는 {single_schedule.doctor.name}입니다.{phone_info}"
                                        else:
                                            schedule_info = []
                                            for s in schedules:
                                                phone_info = f" (연락처: {s.doctor.phone_number})" if s.doctor.phone_number else ""
                                                schedule_info.append(f"• {s.work_schedule}: {s.doctor.name}{phone_info}")
                                            response_part = f"[{date}] {context.last_department} 당직표:\n" + "\n".join(schedule_info)
                                    else:
                                        phone_info = f" (연락처: {schedules.doctor.phone_number})" if schedules.doctor.phone_number else ""
                                        response_part = f"[{date}] {context.last_department} {schedules.work_schedule}는 {schedules.doctor.name}입니다.{phone_info}"
                                    responses.append(response_part)
                                else:
                                    responses.append(f"[{date}] {context.last_department}의 당직 정보를 찾을 수 없습니다.")
                            
                            response_text = "\n\n".join(responses)
                            print(f"===== 다중 날짜 최종 응답: {response_text[:100]}... =====")
                            
                            # 맥락 업데이트 (마지막 날짜로 설정)
                            entities = {
                                'department': context.last_department,
                                'role': context.last_role or '당직의',
                                'date': dates[-1]  # 마지막 날짜로 설정 (모레)
                            }
                            context.update_context(entities, message, response_text)
                            
                            response_time = (time.time() - start_time) * 1000
                            return create_chatbot_response_with_logging(
                                response_text=response_text,
                                session_id=session_id,
                                message=message,
                                response_time=response_time,
                                client_ip=client_ip,
                                entities=entities
                            )
                        
                        else:
                            # 단일 날짜 처리
                            print(f"===== 후속 질문 - 시간 참조 '{time_ref}' -> 날짜 '{target_date}' =====")
                            
                            # 이전 맥락의 부서와 역할 사용
                            entities = {
                                'department': context.last_department,
                                'role': context.last_role or '당직의',
                                'date': target_date
                            }
                            
                            print(f"===== 후속 질문 - 구성된 엔티티: {entities} =====")
                            
                            # DB에서 직접 조회
                            try:
                                print(f"===== DB 조회 시작 =====")
                                print(f"     날짜: {entities['date']}")
                                print(f"     부서: {entities['department']}")
                                print(f"     역할: {entities['role']}")
                                
                                # 후속 질문에서는 역할을 None으로 설정하여 해당 부서의 모든 당직을 조회
                                schedule = await get_schedule_from_db_async(
                                    entities['date'], 
                                    entities['department'], 
                                    None,  # role_name - 후속 질문에서는 모든 역할 포함
                                    None,  # time_range
                                    False,  # night_shift
                                    None   # specific_hour
                                )
                                
                                print(f"===== DB 조회 결과: {schedule} =====")
                                
                                if schedule:
                                    # 단일 스케줄인 경우와 리스트인 경우 모두 처리
                                    if isinstance(schedule, list):
                                        if len(schedule) == 1:
                                            # 단일 결과인 경우
                                            single_schedule = schedule[0]
                                            phone_info = f" (연락처: {single_schedule.doctor.phone_number})" if single_schedule.doctor.phone_number else ""
                                            response_text = f"[{entities['date']}] {entities['department']} {single_schedule.work_schedule}는 {single_schedule.doctor.name}입니다.{phone_info}"
                                        else:
                                            # 다중 결과인 경우 - 전체 당직표 형태로 응답
                                            schedule_info = []
                                            for s in schedule:
                                                phone_info = f" (연락처: {s.doctor.phone_number})" if s.doctor.phone_number else ""
                                                schedule_info.append(f"• {s.work_schedule}: {s.doctor.name}{phone_info}")
                                            response_text = f"[{entities['date']}] {entities['department']} 당직표:\n\n" + "\n".join(schedule_info)
                                    else:
                                        # 단일 스케줄 객체인 경우
                                        phone_info = f" (연락처: {schedule.doctor.phone_number})" if schedule.doctor.phone_number else ""
                                        response_text = f"[{entities['date']}] {entities['department']} {schedule.work_schedule}는 {schedule.doctor.name}입니다.{phone_info}"
                                    
                                    print(f"===== 후속 질문 처리 성공 - 응답: {response_text} =====")
                                    
                                    # 세션 맥락 업데이트
                                    context.update_context(entities, message, response_text)
                                    
                                    response_time = (time.time() - start_time) * 1000
                                    return create_chatbot_response_with_logging(
                                        response_text=response_text,
                                        session_id=session_id,
                                        message=message,
                                        response_time=response_time,
                                        client_ip=client_ip,
                                        entities=entities
                                    )
                                else:
                                    print(f"===== DB 조회 결과 없음 =====")
                                    response_text = f"[{entities['date']}] {entities['department']}에는 해당 날짜에 당직 정보가 없습니다."
                                    
                                    # 세션 맥락 업데이트
                                    context.update_context(entities, message, response_text)
                                    
                                    response_time = (time.time() - start_time) * 1000
                                    return create_chatbot_response_with_logging(
                                        response_text=response_text,
                                        session_id=session_id,
                                        message=message,
                                        response_time=response_time,
                                        client_ip=client_ip,
                                        entities=entities
                                    )
                            except Exception as e:
                                print(f"===== 후속 질문 처리 중 DB 조회 오류: {e} =====")
                                import traceback
                                traceback.print_exc()
                                
                                # 후속 질문 처리 실패 시 명확한 에러 메시지 반환
                                response_text = f"죄송합니다. '{context.last_department}'의 {time_ref} 당직 정보를 조회하는 중 오류가 발생했습니다. 다시 시도해 주세요."
                                response_time = (time.time() - start_time) * 1000
                                return create_chatbot_response_with_logging(
                                    response_text=response_text,
                                    session_id=session_id,
                                    message=message,
                                    response_time=response_time,
                                    client_ip=client_ip,
                                    entities={'followup_error': True}
                                )
                    else:
                        print(f"===== 시간 참조 추출 실패 =====")
                        response_text = f"죄송합니다. '{message}'에서 시간 참조를 파악할 수 없습니다. '내일은?', '다음주는?' 등으로 질문해 주세요."
                        response_time = (time.time() - start_time) * 1000
                        return create_chatbot_response_with_logging(
                            response_text=response_text,
                            session_id=session_id,
                            message=message,
                            response_time=response_time,
                            client_ip=client_ip,
                            entities={'followup_time_parse_error': True}
                        )
            else:
                print(f"===== 이전 부서 정보 없음 - 후속 질문이지만 맥락이 없음 =====")
                response_text = f"이전 대화에서 부서 정보를 찾을 수 없습니다. '순환기내과 당직' 같이 부서명을 포함해서 다시 질문해 주세요."
                response_time = (time.time() - start_time) * 1000
                return create_chatbot_response_with_logging(
                    response_text=response_text,
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities={'followup_no_context': True}
                )
        else:
            print("===== 일반 질문으로 처리 =====")
        
        # 부서 연락처 질문인지 우선 확인 (더 일반적인 패턴)
        # "정형외과 당직의 번호는?" 같은 패턴을 정확히 매칭
        # 부서명과 역할을 분리해서 추출
        dept_contact_pattern = re.search(r'(?:지금|현재)?\s*([가-힣\s]+(?:과|실|센터|부서|당직의|담당의))\s*(?:연락처|전화번호|번호)\s*(?:알려줘|뭐야|는|은)', message)
        if dept_contact_pattern:
            dept_mention = dept_contact_pattern.group(1).strip()
            # "지금"이나 "현재" 같은 시간 키워드 제거
            dept_mention_clean = re.sub(r'^(?:지금|현재)\s*', '', dept_mention).strip()
            # 부서명에서 역할 부분 제거 ("당직의", "담당의" 등)
            dept_mention_clean = re.sub(r'\s*(?:당직의|담당의|수술의)\s*$', '', dept_mention_clean).strip()
            print(f"===== 부서 연락처 질문 감지: '{dept_mention}' → 정리: '{dept_mention_clean}' =====")
            
            # 부서명 매칭 시도 (더 정확한 매칭)
            departments = await get_all_departments_async()
            print(f"     전체 부서 목록: {departments}")
            
            # 동적 별칭 매핑 생성
            department_aliases = await generate_department_aliases_async(departments)
            
            matched_dept = None
            
            # 0. 별칭 매핑 먼저 확인 (정확한 단어 매칭)
            for alias, official_name in department_aliases.items():
                # 단어 경계를 고려한 정확한 매칭
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, dept_mention_clean):
                    matched_dept = official_name
                    print(f"     ✅ 부서 별칭 매핑: '{alias}' → '{official_name}'")
                    break
            
            # 부서명을 길이 기준으로 내림차순 정렬 (더 구체적인 부서명 우선)
            sorted_departments = sorted(departments, key=len, reverse=True)
            print(f"     길이순 정렬된 부서 목록: {sorted_departments}")
            
            # 1. 완전 일치 우선 (dept_mention_clean과 정확히 일치) - 별칭 매핑이 없는 경우만
            if not matched_dept:
                for dept in sorted_departments:
                    if dept == dept_mention_clean:
                        matched_dept = dept
                        print(f"     ✅ 완전 일치: '{dept}'")
                        break
            
            # 2. 추출된 부서명에서 부서명 포함 여부 확인 (더 구체적인 것 우선)
            if not matched_dept:
                for dept in sorted_departments:
                    if dept in dept_mention_clean:
                        matched_dept = dept
                        print(f"     ✅ 추출된 부서명에서 매칭: '{dept}' in '{dept_mention_clean}'")
                        break
            
            # 3. 전체 메시지에서 부서명 매칭 (더 구체적인 것 우선)
            if not matched_dept:
                for dept in sorted_departments:
                    if dept in message:
                        matched_dept = dept
                        print(f"     ✅ 전체 메시지에서 매칭: '{dept}' in '{message}'")
                        break
            
            # 4. 부분 매칭 (공백 제거 후 비교, 더 구체적인 것 우선)
            if not matched_dept:
                for dept in sorted_departments:
                    if dept.replace(" ", "") in message.replace(" ", ""):
                        matched_dept = dept
                        print(f"     ✅ 부분 매칭: '{dept}' (공백 제거 후)")
                        break
            
            if matched_dept:
                print(f"===== 매칭된 부서: '{matched_dept}' =====")
                # 질문에서 추출된 날짜 사용 (없으면 오늘 날짜)
                query_date = entities.get('date', datetime.now().strftime('%Y-%m-%d'))
                print(f"     질문 날짜: {query_date}")
                
                schedules = await get_schedule_from_db_async(
                    query_date, matched_dept, None, None, False, None
                )
                
                if schedules and isinstance(schedules, list) and len(schedules) > 0:
                    # 시간과 상관없이 첫 번째 스케줄 사용 ("오늘"과 "지금" 동일하게 처리)
                    current_schedule = schedules[0]
                    
                    doctor_name = current_schedule.doctor.name
                    phone_number = current_schedule.doctor.phone_number
                    work_schedule = format_work_schedule(current_schedule.work_schedule)
                    
                    # 날짜 포맷팅
                    try:
                        date_obj = datetime.strptime(query_date, '%Y-%m-%d')
                        formatted_date = date_obj.strftime('%m월 %d일')
                    except:
                        formatted_date = query_date
                    
                    if phone_number:
                        response_text = f"[{formatted_date}] {matched_dept} 당직의({doctor_name})의 연락처는 {phone_number}입니다.\n• 당직 시간: {work_schedule}"
                    else:
                        response_text = f"[{formatted_date}] {matched_dept} 당직의는 {doctor_name}이지만 연락처 정보가 등록되어 있지 않습니다.\n• 당직 시간: {work_schedule}"
                    
                    entities = {'department': matched_dept, 'contact_request': True, 'doctor_name': doctor_name}
                    context.update_context(entities, message, response_text)
                    
                    response_time = (time.time() - start_time) * 1000
                    return create_chatbot_response_with_logging(
                        response_text=response_text,
                        session_id=session_id,
                        message=message,
                        response_time=response_time,
                        client_ip=client_ip,
                        entities=entities
                    )
                else:
                    response_text = f"{matched_dept}에는 오늘 당직 정보가 없습니다."
                    entities = {'department': matched_dept, 'contact_request': True, 'no_schedule': True}
            else:
                # 부서 매칭 실패 시 관련 부서 추천
                response_text, extra_entities = await suggest_related_departments(message, dept_mention_clean)
                entities = {'contact_request': True, 'unmatched_department': True, **extra_entities}
            
            context.update_context(entities, message, response_text)
            response_time = (time.time() - start_time) * 1000
            return create_chatbot_response_with_logging(
                response_text=response_text,
                session_id=session_id,
                message=message,
                response_time=response_time,
                client_ip=client_ip,
                entities=entities
            )

        # 의사 연락처 질문인지 확인 (개별 의사명이 명확한 경우) - 연락처 키워드가 있을 때만
        contact_keywords = ['연락처', '전화번호', '번호', '폰']
        is_contact_request = any(keyword in message for keyword in contact_keywords)
        
        if is_contact_request:
            doctor_name = extract_doctor_name_from_message(message)
            if doctor_name:
                print(f"===== 의사 연락처 질문 감지: {doctor_name} =====")
                doctor_info = await get_doctor_info_async(doctor_name)
                
                if doctor_info and doctor_info.phone_number:
                    response_text = f"{doctor_name} 의사의 연락처는 {doctor_info.phone_number}입니다."
                    print(f"===== 의사 연락처 응답: {response_text} =====")
                elif doctor_info:
                    response_text = f"{doctor_name} 의사의 연락처 정보가 등록되어 있지 않습니다."
                else:
                    response_text = f"죄송합니다. {doctor_name} 의사의 정보를 찾을 수 없습니다."
                
                entities = {'doctor_name': doctor_name, 'contact_request': True}
                context.update_context(entities, message, response_text)
                
                response_time = (time.time() - start_time) * 1000
                return create_chatbot_response_with_logging(
                    response_text=response_text,
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities=entities
                )
        
        # 개인별 의사 스케줄 질문인지 확인
        if is_doctor_schedule_question(message):
            doctor_name = extract_doctor_name_for_schedule(message)
            if doctor_name:
                print(f"===== 개인별 스케줄 질문 감지: {doctor_name} =====")
                
                # 날짜 엔티티도 추출 (의사 이름 기반 질문에서도 월 정보 고려)
                date_str = parse_date_reference(message)
                print(f"     추출된 날짜: {date_str}")
                
                # 해당 의사의 스케줄 조회 (날짜 고려)
                schedule_data = await get_doctor_monthly_schedule_async(doctor_name, date_str)
                
                if schedule_data:
                    # 스케줄 데이터를 포맷팅하여 응답 생성
                    response_text = format_doctor_monthly_schedule(schedule_data)
                    print(f"===== 개인별 스케줄 응답: {response_text[:100]}... =====")
                else:
                    response_text = f"죄송합니다. {doctor_name} 의사의 정보를 찾을 수 없습니다."
                
                entities = {'doctor_name': doctor_name, 'schedule_request': True}
                if date_str:
                    entities['date'] = date_str
                context.update_context(entities, message, response_text)
                
                response_time = (time.time() - start_time) * 1000
                return create_chatbot_response_with_logging(
                    response_text=response_text,
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities=entities
                )
            else:
                # 스케줄 질문으로 감지되었지만 의사 이름을 추출하지 못한 경우
                response_text = "의사 이름을 정확히 입력해주세요.\n\n💡 예제 질문: '조준환 교수님 당직 언제야?'"
                
                entities = {'schedule_request': True, 'name_extraction_failed': True}
                context.update_context(entities, message, response_text)
                
                response_time = (time.time() - start_time) * 1000
                return create_chatbot_response_with_logging(
                    response_text=response_text,
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities=entities
                )
        
        # 일반 엔티티 추출 및 처리 (기존 로직)
        # 1. 엔티티 추출
        try:
            entities = await extract_entities(message)
            print(f"추출된 엔티티: {entities}")
            
            # 시스템 관련 질문 직접 처리
            system_patterns = [
                r'너는?\s*누구', r'당신은?\s*누구', r'너는?\s*뭐', r'당신은?\s*뭐',
                r'너의?\s*이름', r'당신의?\s*이름', r'자기소개', r'소개해',
                r'너는?\s*어떤', r'당신은?\s*어떤'
            ]
            
            is_system_question = any(re.search(pattern, message) for pattern in system_patterns)
            
            if is_system_question:
                response_time = (time.time() - start_time) * 1000
                response_text = "안녕하세요! 저는 당직 의료진 정보를 안내하는 챗봇입니다. \n\n다음과 같은 질문에 도움을 드릴 수 있습니다:\n• 오늘/내일 당직 의사는 누구인가요?\n• 신경과 당직의 연락처를 알려주세요\n• 지금 응급실 당직의는 누구인가요?\n• 특정 날짜의 당직표를 확인해주세요\n\n궁금한 것이 있으시면 언제든 물어보세요! 😊"
                return create_chatbot_response_with_logging(
                    response_text=response_text,
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities={'system_question': True}
                )
            
            # 이미 extract_entities에서 날짜 조정을 완료했으므로 여기서는 제거
            
            # date 엔티티만 추출된 경우 처리 (부서, 역할, 의사명이 모두 없는 경우)
            has_only_date = (
                entities.get('date') and 
                not entities.get('department') and 
                not entities.get('role') and 
                not entities.get('doctor_name') and
                not entities.get('date_question')  # 날짜 질문은 제외
            )
            
            if has_only_date:
                response_time = (time.time() - start_time) * 1000
                
                # 날짜 포맷팅
                try:
                    date_obj = datetime.strptime(entities['date'], '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%m월 %d일')
                except:
                    formatted_date = entities['date']
                
                response_text = f"""📅 무엇을 알고 싶으신가요?

구체적으로 질문해 주세요:

💡 예제 질문:
• "8월 6일 신경과 당직 누구야?"
• "08월 06일 응급실 당직의 연락처 알려줘"
• "오늘 외과 수술의는 누구인가요?"
• "2025-08-06 내과 당직의는 누구인가요?"

부서명이나 역할을 포함해서 다시 질문해 주세요! 🏥"""
                
                return create_chatbot_response_with_logging(
                    response_text=response_text,
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities={'date_only': True, 'needs_specific_info': True}
                )
            
        except Exception as e:
            print(f"엔티티 추출 오류: {e}")
            
            # 엔티티 추출이 실패하면 RAG 기반 응답으로 대체
            try:
                print("엔티티 추출 실패, RAG로 대체합니다...")
                rag_request = RAGRequest(query=message, max_results=10)
                rag_response = await rag_query(rag_request)
                
                response_time = (time.time() - start_time) * 1000
                
                if rag_response.get("status") == "success" and "answer" in rag_response:
                    response_text = rag_response["answer"]
                else:
                    response_text = rag_response.get("message", "죄송합니다. 답변을 생성할 수 없습니다.")
                    
                return create_chatbot_response_with_logging(
                    response_text=response_text,
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities={'entity_extraction_failed': True}
                )
                
            except Exception as rag_error:
                print(f"RAG 대체 시도 오류: {rag_error}")
                response_time = (time.time() - start_time) * 1000
                error_text = f"엔티티 추출 및 RAG 응답 생성 중 오류가 발생했습니다: {str(e)}"
                
                return create_chatbot_response_with_logging(
                    response_text=error_text,
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities={'error': True, 'entity_extraction_failed': True}
                )
        
        # 날짜 질문 처리
        if "date_question" in entities:
            today = datetime.now()
            weekday_map = {0: '월요일', 1: '화요일', 2: '수요일', 3: '목요일', 4: '금요일', 5: '토요일', 6: '일요일'}
            weekday = weekday_map[today.weekday()]
            response_text = f"오늘은 {today.strftime('%Y년 %m월 %d일')} {weekday}입니다."
            
            response_time = (time.time() - start_time) * 1000
            return create_chatbot_response_with_logging(
                response_text=response_text,
                session_id=session_id,
                message=message,
                response_time=response_time,
                client_ip=client_ip,
                entities=entities
            )
        
        # 부서 목록 질문 처리
        department_list_keywords = [
            "어떤 과", "무슨 과", "어떤 부서", "무슨 부서", "어느 과", "어느 부서",
            "과 목록", "부서 목록", "과 리스트", "부서 리스트", 
            "과가 있", "부서가 있", "과가 뭐", "부서가 뭐",
            "과를 알려", "부서를 알려", "과 알려", "부서 알려",
            "과 종류", "부서 종류", "과명", "부서명",
            "진료과", "진료부서", "어떤 진료과", "무슨 진료과",
            "과 전체", "부서 전체", "모든 과", "모든 부서",
            "과는 뭐", "부서는 뭐", "과는 무엇", "부서는 무엇"
        ]
        if any(keyword in message.lower() for keyword in department_list_keywords):
            try:
                departments = await get_all_departments_async()
                response_time = (time.time() - start_time) * 1000
                
                if departments:
                    dept_list = '\n'.join([f"• {dept}" for dept in departments])
                    response_text = f"📋 현재 등록된 부서 목록:\n\n{dept_list}\n\n💡 예제 질문: \"오늘 순환기내과 당직 누구야?\""
                else:
                    response_text = "등록된 부서 정보가 없습니다."
                    
                return create_chatbot_response_with_logging(
                    response_text=response_text,
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities=entities if 'entities' in locals() else {'department_list_query': True}
                )
            except Exception as e:
                print(f"부서 목록 조회 오류: {e}")
                response_time = (time.time() - start_time) * 1000
                return create_chatbot_response_with_logging(
                    response_text="부서 목록을 가져오는 중 오류가 발생했습니다.",
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities={'error': True, 'department_list_query': True}
                )
        
        # 날짜만 있고 다른 키워드가 없는 경우 처리 (예: "7/2")
        if ('date' in entities and 
            'role' not in entities and 
            'department' not in entities and 
            'time_range' not in entities and
            'phone_requested' not in entities and
            'unmatched_department' not in entities):
            
            # 메시지에 당직/의사/담당 관련 키워드가 있는지 확인
            medical_keywords = ['당직', '의사', '담당', '수술', '근무', '병동', '중환자실', '응급', '외래']
            has_medical_keyword = any(keyword in message for keyword in medical_keywords)
            
            if not has_medical_keyword:
                date_str = entities.get("date")
                # 날짜 포맷팅
                try:
                    from datetime import datetime as date_parser
                    parsed_date = date_parser.strptime(date_str, '%Y-%m-%d')
                    formatted_date = parsed_date.strftime('%m월 %d일')
                except:
                    formatted_date = date_str
                
                response_text = f"📅 {formatted_date}에 대해 무엇을 알고 싶으신가요?\n\n💡 구체적으로 질문해 주세요:\n• \"{formatted_date} 외과 당직 누구야?\"\n• \"{formatted_date} 당직표 보여줘\"\n• \"{formatted_date} 응급실 담당의사는?\""
                
                response_time = (time.time() - start_time) * 1000
                return create_chatbot_response_with_logging(
                    response_text=response_text,
                    session_id=session_id,
                    message=message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities=entities
                )
        
        # 부서명이 매칭되지 않은 경우 처리 - 관련 부서 추천
        if entities.get("unmatched_department"):
            print(f"===== 부서 추천 시스템 시작 =====")
            
            from schedule.models import Department
            all_departments = list(Department.objects.values_list('name', flat=True))
            query_dept = entities.get("query_dept")  # extract_entities에서 추출한 부서명
            
            print(f"추출된 질문 부서명: '{query_dept}'")
            print(f"사용 가능한 전체 부서 수: {len(all_departments)}개")
            
            if query_dept and all_departments:
                # 추천 시스템 사용
                similar_depts = find_similar_departments(query_dept, all_departments)
                
                if similar_depts:
                    # 유사한 부서들을 찾은 경우
                    response_text = create_department_recommendation_response(query_dept, similar_depts)
                    print(f"✅ 부서 추천 완료: {len(similar_depts)}개 부서 추천")
                else:
                    # 유사한 부서를 찾지 못한 경우
                    dept_list = "\n".join([f"• {dept}" for dept in sorted(all_departments)[:15]])
                    more_count = max(0, len(all_departments) - 15)
                    more_text = f"\n... 외 {more_count}개 더" if more_count > 0 else ""
                    
                    response_text = f"""'{query_dept}'와 관련된 진료과를 찾을 수 없습니다.

사용 가능한 진료과 목록:
{dept_list}{more_text}

정확한 진료과명으로 다시 질문해 주세요!
💡 예시: "신경과 당직 누구야?" """
                    print(f"❌ '{query_dept}' 관련 부서 추천 실패 - 전체 목록 제공")
            else:
                # 부서명을 추출하지 못했거나 DB 오류인 경우
                if all_departments:
                    dept_list = "\n".join([f"• {dept}" for dept in sorted(all_departments)[:15]])
                    more_count = max(0, len(all_departments) - 15)
                    more_text = f"\n... 외 {more_count}개 더" if more_count > 0 else ""
                    
                    response_text = f"""진료과명을 명확히 입력해 주세요.

사용 가능한 진료과 목록:
{dept_list}{more_text}

정확한 진료과명으로 다시 질문해 주세요!
💡 예시: "신경과 당직 누구야?" """
                else:
                    response_text = "진료과 정보를 불러올 수 없습니다."
                
                print(f"❌ 부서명 추출 실패 또는 DB 오류 - 기본 안내 제공")
            
            response_time = (time.time() - start_time) * 1000
            return create_chatbot_response_with_logging(
                response_text=response_text,
                session_id=session_id,
                message=message,
                response_time=response_time,
                client_ip=client_ip,
                entities={'department_recommendation': True, 'query_dept': query_dept}
            )
        
        # 매핑된 부서에 스케줄이 없는 경우 대안 제시
        if "department" in entities:
            try:
                dept_name = entities["department"]
                date_str = entities.get("date", datetime.now().strftime('%Y-%m-%d'))
                
                # 해당 부서에 스케줄이 있는지 미리 확인
                dept_obj = await sync_to_async(Department.objects.get)(name=dept_name)
                has_schedule = await sync_to_async(Schedule.objects.filter(
                    doctor__department=dept_obj,
                    date=date_str
                ).exists)()
                
                if not has_schedule:
                    # 동적으로 관련 부서 찾기
                    user_keywords = extract_dept_keywords(message)
                    print(f"관련 부서 찾기 - 추출된 키워드: {user_keywords}")
                    
                    # 키워드가 포함된 다른 부서들 찾기
                    related_depts = []
                    all_departments = await get_all_departments_async()
                    for dept in all_departments:
                        if dept != dept_name:  # 원래 부서 제외
                            # 키워드가 포함된 부서 찾기
                            for keyword in user_keywords:
                                if keyword in dept:
                                    related_depts.append(dept)
                                    break
                    
                    print(f"찾은 관련 부서: {related_depts}")
                    
                    if related_depts:
                        # 관련 부서 중에서 스케줄이 있는 부서 찾기
                        available_depts = []
                        for related_dept in related_depts:
                            try:
                                related_dept_obj = await sync_to_async(Department.objects.get)(name=related_dept)
                                has_related_schedule = await sync_to_async(Schedule.objects.filter(
                                    doctor__department=related_dept_obj,
                                    date=date_str
                                ).exists)()
                                if has_related_schedule:
                                    available_depts.append(related_dept)
                            except:
                                pass
                        
                        if available_depts:
                            dept_list = '\n'.join([f"• {dept}" for dept in available_depts])
                            response_text = f"⚠️ {dept_name}에는 {date_str}에 당직 정보가 없습니다.\n\n📋 대신 다음 관련 부서를 확인해보세요:\n\n{dept_list}\n\n💡 예제 질문: \"오늘 {available_depts[0]} 당직 누구야?\""
                        else:
                            # 관련 부서도 없으면 전체 부서 목록 제공
                            departments = await get_all_departments_async()
                            dept_list = '\n'.join([f"• {dept}" for dept in departments])
                            response_text = f"⚠️ {dept_name}에는 {date_str}에 당직 정보가 없습니다.\n\n📋 다른 부서를 확인해보세요:\n\n{dept_list}\n\n💡 예제 질문: \"오늘 순환기내과 당직 누구야?\""
                        
                        response_time = (time.time() - start_time) * 1000
                        return create_chatbot_response_with_logging(
                            response_text=response_text,
                            session_id=session_id,
                            message=message,
                            response_time=response_time,
                            client_ip=client_ip,
                            entities=entities
                        )
                    
            except Exception as e:
                print(f"부서 스케줄 확인 오류: {e}")
                pass  # 에러 발생 시 기본 로직으로 진행
        
        # 2. 스케줄 조회 전략 결정
        # 기본적으로 날짜와 부서 정보가 있으면 직접 DB 조회 우선
        should_query_db_directly = False
        
        # 날짜와 부서 정보가 모두 있으면 직접 DB 조회
        if 'date' in entities and 'department' in entities:
            should_query_db_directly = True
            print("날짜와 부서 정보가 모두 있어 직접 DB 조회를 우선합니다.")
        
        # 벡터 검색 결과
        search_results = None
        
        # 3. DB 직접 조회 우선 시도
        if should_query_db_directly:
            try:
                date_str = entities.get("date")
                dept_name = entities.get("department")
                role_name = entities.get("role")
                time_range = entities.get("time_range")
                night_shift = entities.get("night_shift", False)
                specific_hour = entities.get("specific_hour")
                
                print(f"Django DB 직접 검색: 날짜={date_str}, 부서={dept_name}, 역할={role_name}, 시간대={time_range}, 야간근무={night_shift}, 특정시간={specific_hour}")
                
                # 시간이나 역할이 특정되지 않은 경우, 전체 당직표 반환 모드로 설정
                # '당직의'라는 일반적인 역할은 시간 특정이 없으면 모든 당직을 보여주기 위해 무시
                is_general_role = role_name in ['당직의', '담당의']
                show_all_schedules = specific_hour is None and not time_range
                
                # '지금' 키워드가 있으면 현재 시간에 해당하는 근무대만 반환
                if "지금" in message or "현재" in message:
                    print("'지금' 키워드 감지 - 현재 시간에 해당하는 근무대만 반환")
                    specific_hour = entities.get('current_hour')
                    show_all_schedules = False
                    print(f"현재 시간({specific_hour}시)에 해당하는 근무대 검색")
                
                if is_general_role and show_all_schedules:
                    print("일반적인 역할(당직의/담당의)과 시간 특정이 없어 전체 당직표를 조회합니다.")
                    # 역할을 None으로 설정하여 모든 스케줄을 가져오도록 함
                    role_name = None
                
                # Django 모델에서 직접 조회
                schedule_result = await get_schedule_from_db_async(date_str, dept_name, role_name, time_range, night_shift, specific_hour)
                
                if schedule_result:
                    # 시간이 특정되지 않은 경우, 전체 당직표 반환
                    if isinstance(schedule_result, list) and show_all_schedules:
                        print(f"해당 날짜/부서의 모든 스케줄을 반환합니다. 스케줄 수: {len(schedule_result)}")
                        
                        # 시간 순으로 정렬
                        sorted_schedules = sorted(schedule_result, 
                                                key=lambda s: int(str(s.work_schedule).split(' - ')[0].split(':')[0]))
                        
                        schedule_info = [f"• {format_work_schedule(s.work_schedule)}: {s.doctor.name} (연락처: {s.doctor.phone_number})" 
                                       for s in sorted_schedules]
                        
                        response_text = f"[{date_str}] {dept_name} 당직표:\n\n" + "\n".join(schedule_info)
                        print(f"응답: {response_text}")
                        response_time = (time.time() - start_time) * 1000
                        return create_chatbot_response_with_logging(
                            response_text=response_text,
                            session_id=session_id,
                            message=message,
                            response_time=response_time,
                            client_ip=client_ip,
                            entities=entities
                        )
                    # 단일 스케줄 반환인 경우
                    else:
                        if isinstance(schedule_result, list):
                            schedule = schedule_result[0]
                        else:
                            schedule = schedule_result
                            
                        print(f"DB 직접 조회 성공: {schedule.date} - {schedule.doctor.name}, 시간={schedule.work_schedule}")
                        # 당직의 정보 질문에는 기본적으로 연락처도 함께 제공
                        phone_info = f" (연락처: {schedule.doctor.phone_number})" if schedule.doctor.phone_number else ""
                        response_text = f"[{date_str}] {dept_name} {format_work_schedule(schedule.work_schedule)}는 {schedule.doctor.name}입니다.{phone_info}"
                        
                        print(f"응답: {response_text}")
                        response_time = (time.time() - start_time) * 1000
                        return create_chatbot_response_with_logging(
                            response_text=response_text,
                            session_id=session_id,
                            message=message,
                            response_time=response_time,
                            client_ip=client_ip,
                            entities=entities
                        )
                else:
                    print(f"DB 직접 조회 실패: {date_str}, {dept_name}에 해당하는 스케줄이 없습니다.")
                    # 벡터 검색으로 폴백
            except Exception as e:
                print(f"DB 직접 조회 오류: {e}")
                import traceback
                traceback.print_exc()
                # 벡터 검색으로 폴백
        
        # 4. 벡터 검색 시도 (FAISS 벡터 스토어가 사용 가능한 경우)
        print(f"===== 벡터 검색 시도 시작 =====")
        print(f"벡터 스토어 상태 확인: {vector_store is not None}")
        if vector_store is not None:
            print(f"벡터 스토어 인덱스 상태: {vector_store.index is not None}, 벡터 수: {vector_store.index.ntotal if vector_store.index else 0}")
            
            # 벡터 수가 0인 경우 명확히 표시
            if vector_store.index and vector_store.index.ntotal == 0:
                print("⚠️ 벡터 DB가 비어있습니다! 벡터 DB 업데이트가 필요합니다.")
                print("   웹 인터페이스에서 '벡터 DB 업데이트' 버튼을 클릭하거나")
                print("   POST /update-vector-db API를 호출하세요.")
            
            try:
                print("벡터 검색 시작...")
                # 메시지 임베딩
                print(f"메시지 임베딩 생성 중: '{message}'")
                query_embedding = model.encode(message).tolist()
                print(f"임베딩 생성 완료. 차원: {len(query_embedding)}")
                
                # 벡터 검색 수행
                print("벡터 검색 수행 중...")
                search_results = vector_store.search(query_embedding, k=20)  # 더 많은 결과 가져오기
                print(f"벡터 검색 완료. 반환된 결과 수: {len(search_results) if search_results else 0}")
                
                if search_results and len(search_results) > 0:
                    print(f"✅ 벡터 검색 결과: {len(search_results)}개 발견")
                    
                    # 상위 결과 로깅
                    for i, result in enumerate(search_results[:10]):  # 상위 10개만 로깅
                        metadata = result["entity"]
                        score = result["distance"]
                        print(f"  {i+1}. 점수: {score:.4f}, 날짜: {metadata.get('date', 'N/A')}, 부서: {metadata.get('department', 'N/A')}, 역할: {metadata.get('role', 'N/A')}, 이름: {metadata.get('name', 'N/A')}")
                    
                    # 날짜와 부서 일치 항목 모두 찾기 (전체 당직표 모드)
                    matching_schedules = []
                    date_dept_match = False
                    
                    if 'date' in entities and 'department' in entities:
                        print(f"날짜({entities['date']})와 부서({entities['department']}) 일치 검색을 통한 전체 당직표 조회")
                        for result in search_results:
                            metadata = result["entity"]
                            if (metadata.get('date') == entities['date'] and 
                                metadata.get('department') == entities['department']):
                                matching_schedules.append(metadata)
                                date_dept_match = True
                        
                        if date_dept_match and len(matching_schedules) > 0:
                            print(f"날짜와 부서 일치 항목 {len(matching_schedules)}개 발견")
                            
                            # 정확한 부서 일치 결과 찾기
                            if 'department' in entities:
                                target_dept = entities['department']
                                print(f"부서 일치 검색: '{target_dept}'")
                                
                                # 먼저 부서와 날짜가 모두 일치하는 항목 찾기
                                for result in search_results:
                                    metadata = result["entity"]
                                    if metadata.get('department') == target_dept:
                                        if 'date' in entities and metadata.get('date') == entities['date']:
                                            best_match = metadata
                                            exact_match = True
                                            print(f"  부서+날짜 일치 항목 발견: {metadata}")
                                            break
                                
                                # 부서만 일치하는 항목 찾기 (날짜 일치 항목이 없는 경우)
                                if not exact_match:
                                    for result in search_results:
                                        metadata = result["entity"]
                                        if metadata.get('department') == target_dept:
                                            best_match = metadata
                                            exact_match = True
                                            print(f"  부서 일치 항목 발견: {metadata}")
                                            break
                        
                        if date_dept_match and len(matching_schedules) > 0:
                            print(f"날짜와 부서 일치 항목 {len(matching_schedules)}개 발견")
                            
                            # 현재 날짜 우선: 먼저 부서와 현재 날짜가 모두 일치하는 항목 찾기
                            today_date = datetime.now().strftime('%Y-%m-%d')
                            
                            for result in search_results:
                                metadata = result["entity"]
                                if (metadata.get('department') == target_dept and 
                                    metadata.get('date') == today_date):
                                    best_match = metadata
                                    exact_match = True
                                    print(f"  부서+오늘날짜 일치 항목 발견: {metadata}")
                                    break
                            
                            # 오늘 날짜가 없으면 부서와 지정된 날짜가 일치하는 항목 찾기
                            if not exact_match and 'date' in entities:
                                target_date = entities['date']
                                for result in search_results:
                                    metadata = result["entity"]
                                    if (metadata.get('department') == target_dept and 
                                        metadata.get('date') == target_date):
                                        best_match = metadata
                                        exact_match = True
                                        print(f"  부서+지정날짜 일치 항목 발견: {metadata}")
                                        break
                                
                                # 그래도 없으면 부서만 일치하는 항목 찾기 (가장 최근 날짜 우선)
                                if not exact_match:
                                    dept_matches = []
                                    for result in search_results:
                                        metadata = result["entity"]
                                        if metadata.get('department') == target_dept:
                                            dept_matches.append(metadata)
                                    
                                    if dept_matches:
                                        # 날짜 기준으로 정렬하여 가장 최근 것 선택
                                        dept_matches.sort(key=lambda x: x.get('date', ''), reverse=True)
                                        best_match = dept_matches[0]
                                        exact_match = True
                                        print(f"  부서 일치 항목 발견 (최근 날짜 우선): {best_match}")
                                
                                # 특정 시간에 해당하는지 확인 (current_hour이 17시인 경우)
                                if best_match and 'current_hour' in entities:
                                    current_hour = entities['current_hour']
                                    role = best_match.get('role', '')
                                    
                                    # 24시간 당직(08:00 - 08:00)인지 확인
                                    if role == "08:00 - 08:00":
                                        print(f"  24시간 당직이므로 현재 시간({current_hour}시)에 근무 중")
                                    else:
                                        # 다른 시간대인 경우 시간 범위 확인
                                        times = role.split(' - ')
                                        if len(times) == 2:
                                            try:
                                                start_hour = int(times[0].split(':')[0])
                                                end_hour = int(times[1].split(':')[0])
                                                
                                                # 시간 범위 확인
                                                in_time_range = False
                                                if end_hour <= start_hour:  # 익일까지 근무
                                                    in_time_range = current_hour >= start_hour or current_hour < end_hour
                                                else:  # 당일 근무
                                                    in_time_range = start_hour <= current_hour < end_hour
                                                
                                                if not in_time_range:
                                                    print(f"  현재 시간({current_hour}시)이 근무 시간({role}) 범위에 없음")
                                                    # 현재 시간에 해당하지 않으면 DB에서 직접 조회 시도
                                                    best_match = None
                                                    exact_match = False
                                            except:
                                                pass  # 파싱 오류 시 그대로 진행
                        
                        if date_dept_match and len(matching_schedules) > 0:
                            print(f"날짜와 부서 일치 항목 {len(matching_schedules)}개 발견")
                            
                            # 현재 날짜 우선: 먼저 부서와 현재 날짜가 모두 일치하는 항목 찾기
                            today_date = datetime.now().strftime('%Y-%m-%d')
                            
                            for result in search_results:
                                metadata = result["entity"]
                                if (metadata.get('department') == target_dept and 
                                    metadata.get('date') == today_date):
                                    best_match = metadata
                                    exact_match = True
                                    print(f"  부서+오늘날짜 일치 항목 발견: {metadata}")
                                    break
                            
                            # 오늘 날짜가 없으면 부서와 지정된 날짜가 일치하는 항목 찾기
                            if not exact_match and 'date' in entities:
                                target_date = entities['date']
                                for result in search_results:
                                    metadata = result["entity"]
                                    if (metadata.get('department') == target_dept and 
                                        metadata.get('date') == target_date):
                                        best_match = metadata
                                        exact_match = True
                                        print(f"  부서+지정날짜 일치 항목 발견: {metadata}")
                                        break
                                
                                # 그래도 없으면 부서만 일치하는 항목 찾기 (가장 최근 날짜 우선)
                                if not exact_match:
                                    dept_matches = []
                                    for result in search_results:
                                        metadata = result["entity"]
                                        if metadata.get('department') == target_dept:
                                            dept_matches.append(metadata)
                                    
                                    if dept_matches:
                                        # 날짜 기준으로 정렬하여 가장 최근 것 선택
                                        dept_matches.sort(key=lambda x: x.get('date', ''), reverse=True)
                                        best_match = dept_matches[0]
                                        exact_match = True
                                        print(f"  부서 일치 항목 발견 (최근 날짜 우선): {best_match}")
                                
                                # 특정 시간에 해당하는지 확인 (current_hour이 17시인 경우)
                                if best_match and 'current_hour' in entities:
                                    current_hour = entities['current_hour']
                                    role = best_match.get('role', '')
                                    
                                    # 24시간 당직(08:00 - 08:00)인지 확인
                                    if role == "08:00 - 08:00":
                                        print(f"  24시간 당직이므로 현재 시간({current_hour}시)에 근무 중")
                                    else:
                                        # 다른 시간대인 경우 시간 범위 확인
                                        times = role.split(' - ')
                                        if len(times) == 2:
                                            try:
                                                start_hour = int(times[0].split(':')[0])
                                                end_hour = int(times[1].split(':')[0])
                                                
                                                # 시간 범위 확인
                                                in_time_range = False
                                                if end_hour <= start_hour:  # 익일까지 근무
                                                    in_time_range = current_hour >= start_hour or current_hour < end_hour
                                                else:  # 당일 근무
                                                    in_time_range = start_hour <= current_hour < end_hour
                                                
                                                if not in_time_range:
                                                    print(f"  현재 시간({current_hour}시)이 근무 시간({role}) 범위에 없음")
                                                    # 현재 시간에 해당하지 않으면 DB에서 직접 조회 시도
                                                    best_match = None
                                                    exact_match = False
                                            except:
                                                pass  # 파싱 오류 시 그대로 진행
                        
                        if date_dept_match and len(matching_schedules) > 0:
                            print(f"날짜와 부서 일치 항목 {len(matching_schedules)}개 발견")
                            
                            # 현재 날짜 우선: 먼저 부서와 현재 날짜가 모두 일치하는 항목 찾기
                            today_date = datetime.now().strftime('%Y-%m-%d')
                            
                            for result in search_results:
                                metadata = result["entity"]
                                if (metadata.get('department') == target_dept and 
                                    metadata.get('date') == today_date):
                                    best_match = metadata
                                    exact_match = True
                                    print(f"  부서+오늘날짜 일치 항목 발견: {metadata}")
                                    break
                            
                            # 오늘 날짜가 없으면 부서와 지정된 날짜가 일치하는 항목 찾기
                            if not exact_match and 'date' in entities:
                                target_date = entities['date']
                                for result in search_results:
                                    metadata = result["entity"]
                                    if (metadata.get('department') == target_dept and 
                                        metadata.get('date') == target_date):
                                        best_match = metadata
                                        exact_match = True
                                        print(f"  부서+지정날짜 일치 항목 발견: {metadata}")
                                        break
                                
                                # 그래도 없으면 부서만 일치하는 항목 찾기 (가장 최근 날짜 우선)
                                if not exact_match:
                                    dept_matches = []
                                    for result in search_results:
                                        metadata = result["entity"]
                                        if metadata.get('department') == target_dept:
                                            dept_matches.append(metadata)
                                    
                                    if dept_matches:
                                        # 날짜 기준으로 정렬하여 가장 최근 것 선택
                                        dept_matches.sort(key=lambda x: x.get('date', ''), reverse=True)
                                        best_match = dept_matches[0]
                                        exact_match = True
                                        print(f"  부서 일치 항목 발견 (최근 날짜 우선): {best_match}")
                                
                                # 특정 시간에 해당하는지 확인 (current_hour이 17시인 경우)
                                if best_match and 'current_hour' in entities:
                                    current_hour = entities['current_hour']
                                    role = best_match.get('role', '')
                                    
                                    # 24시간 당직(08:00 - 08:00)인지 확인
                                    if role == "08:00 - 08:00":
                                        print(f"  24시간 당직이므로 현재 시간({current_hour}시)에 근무 중")
                                    else:
                                        # 다른 시간대인 경우 시간 범위 확인
                                        times = role.split(' - ')
                                        if len(times) == 2:
                                            try:
                                                start_hour = int(times[0].split(':')[0])
                                                end_hour = int(times[1].split(':')[0])
                                                
                                                # 시간 범위 확인
                                                in_time_range = False
                                                if end_hour <= start_hour:  # 익일까지 근무
                                                    in_time_range = current_hour >= start_hour or current_hour < end_hour
                                                else:  # 당일 근무
                                                    in_time_range = start_hour <= current_hour < end_hour
                                                
                                                if not in_time_range:
                                                    print(f"  현재 시간({current_hour}시)이 근무 시간({role}) 범위에 없음")
                                                    # 현재 시간에 해당하지 않으면 DB에서 직접 조회 시도
                                                    best_match = None
                                                    exact_match = False
                                            except:
                                                pass  # 파싱 오류 시 그대로 진행
                        
                        if date_dept_match and len(matching_schedules) > 0:
                            print(f"날짜와 부서 일치 항목 {len(matching_schedules)}개 발견")
                            
                            # 현재 날짜 우선: 먼저 부서와 현재 날짜가 모두 일치하는 항목 찾기
                            today_date = datetime.now().strftime('%Y-%m-%d')
                            
                            for result in search_results:
                                metadata = result["entity"]
                                if (metadata.get('department') == target_dept and 
                                    metadata.get('date') == today_date):
                                    best_match = metadata
                                    exact_match = True
                                    print(f"  부서+오늘날짜 일치 항목 발견: {metadata}")
                                    break
                            
                            # 오늘 날짜가 없으면 부서와 지정된 날짜가 일치하는 항목 찾기
                            if not exact_match and 'date' in entities:
                                target_date = entities['date']
                                for result in search_results:
                                    metadata = result["entity"]
                                    if (metadata.get('department') == target_dept and 
                                        metadata.get('date') == target_date):
                                        best_match = metadata
                                        exact_match = True
                                        print(f"  부서+지정날짜 일치 항목 발견: {metadata}")
                                        break
                            
                            # 그래도 없으면 부서만 일치하는 항목 찾기 (가장 최근 날짜 우선)
                            if not exact_match:
                                dept_matches = []
                                for result in search_results:
                                    metadata = result["entity"]
                                    if metadata.get('department') == target_dept:
                                        dept_matches.append(metadata)
                                
                                if dept_matches:
                                    # 날짜 기준으로 정렬하여 가장 최근 것 선택
                                    dept_matches.sort(key=lambda x: x.get('date', ''), reverse=True)
                                    best_match = dept_matches[0]
                                    exact_match = True
                                    print(f"  부서 일치 항목 발견 (최근 날짜 우선): {best_match}")
                            
                            # 특정 시간에 해당하는지 확인 (current_hour이 17시인 경우)
                            if best_match and 'current_hour' in entities:
                                current_hour = entities['current_hour']
                                role = best_match.get('role', '')
                                
                                # 24시간 당직(08:00 - 08:00)인지 확인
                                if role == "08:00 - 08:00":
                                    print(f"  24시간 당직이므로 현재 시간({current_hour}시)에 근무 중")
                                else:
                                    # 다른 시간대인 경우 시간 범위 확인
                                    times = role.split(' - ')
                                    if len(times) == 2:
                                        try:
                                            start_hour = int(times[0].split(':')[0])
                                            end_hour = int(times[1].split(':')[0])
                                            
                                            # 시간 범위 확인
                                            in_time_range = False
                                            if end_hour <= start_hour:  # 익일까지 근무
                                                in_time_range = current_hour >= start_hour or current_hour < end_hour
                                            else:  # 당일 근무
                                                in_time_range = start_hour <= current_hour < end_hour
                                            
                                            if not in_time_range:
                                                print(f"  현재 시간({current_hour}시)이 근무 시간({role}) 범위에 없음")
                                                # 현재 시간에 해당하지 않으면 DB에서 직접 조회 시도
                                                best_match = None
                                                exact_match = False
                                        except:
                                            pass  # 파싱 오류 시 그대로 진행
                        
                        if date_dept_match and len(matching_schedules) > 0:
                            print(f"날짜와 부서 일치 항목 {len(matching_schedules)}개 발견")
                            
                            # 현재 날짜 우선: 먼저 부서와 현재 날짜가 모두 일치하는 항목 찾기
                            today_date = datetime.now().strftime('%Y-%m-%d')
                            
                            for result in search_results:
                                metadata = result["entity"]
                                if (metadata.get('department') == target_dept and 
                                    metadata.get('date') == today_date):
                                    best_match = metadata
                                    exact_match = True
                                    print(f"  부서+오늘날짜 일치 항목 발견: {metadata}")
                                    break
                            
                            # 오늘 날짜가 없으면 부서와 지정된 날짜가 일치하는 항목 찾기
                            if not exact_match and 'date' in entities:
                                target_date = entities['date']
                                for result in search_results:
                                    metadata = result["entity"]
                                    if (metadata.get('department') == target_dept and 
                                        metadata.get('date') == target_date):
                                        best_match = metadata
                                        exact_match = True
                                        print(f"  부서+지정날짜 일치 항목 발견: {metadata}")
                                        break
                            
                            # 그래도 없으면 부서만 일치하는 항목 찾기 (가장 최근 날짜 우선)
                            if not exact_match:
                                dept_matches = []
                                for result in search_results:
                                    metadata = result["entity"]
                                    if metadata.get('department') == target_dept:
                                        dept_matches.append(metadata)
                                
                                if dept_matches:
                                    # 날짜 기준으로 정렬하여 가장 최근 것 선택
                                    dept_matches.sort(key=lambda x: x.get('date', ''), reverse=True)
                                    best_match = dept_matches[0]
                                    exact_match = True
                                    print(f"  부서 일치 항목 발견 (최근 날짜 우선): {best_match}")
                            
                            # 특정 시간에 해당하는지 확인 (current_hour이 17시인 경우)
                            if best_match and 'current_hour' in entities:
                                current_hour = entities['current_hour']
                                role = best_match.get('role', '')
                                
                                # 24시간 당직(08:00 - 08:00)인지 확인
                                if role == "08:00 - 08:00":
                                    print(f"  24시간 당직이므로 현재 시간({current_hour}시)에 근무 중")
                                else:
                                    # 다른 시간대인 경우 시간 범위 확인
                                    times = role.split(' - ')
                                    if len(times) == 2:
                                        try:
                                            start_hour = int(times[0].split(':')[0])
                                            end_hour = int(times[1].split(':')[0])
                                            
                                            # 시간 범위 확인
                                            in_time_range = False
                                            if end_hour <= start_hour:  # 익일까지 근무
                                                in_time_range = current_hour >= start_hour or current_hour < end_hour
                                            else:  # 당일 근무
                                                in_time_range = start_hour <= current_hour < end_hour
                                            
                                            if not in_time_range:
                                                print(f"  현재 시간({current_hour}시)이 근무 시간({role}) 범위에 없음")
                                                # 현재 시간에 해당하지 않으면 DB에서 직접 조회 시도
                                                best_match = None
                                                exact_match = False
                                        except:
                                            pass  # 파싱 오류 시 그대로 진행
                            
                            # best_match가 있으면 바로 응답 반환
                            if best_match:
                                # 당직의 정보 질문에는 기본적으로 연락처도 함께 제공
                                phone_info = f" (연락처: {best_match['phone']})" if best_match.get('phone') else ""
                                response_text = f"[{best_match['date']}] {best_match['department']} {format_work_schedule(best_match['role'])}는 {best_match['name']}입니다.{phone_info}"
                                
                                print(f"응답: {response_text}")
                                response_time = (time.time() - start_time) * 1000
                                return create_chatbot_response_with_logging(
                                    response_text=response_text,
                                    session_id=session_id,
                                    message=message,
                                    response_time=response_time,
                                    client_ip=client_ip,
                                    entities=entities
                                )
                            
                                                    # 전체 당직표 모드
                        # 시간 순으로 정렬 (시작 시간 기준)
                        matching_schedules.sort(key=lambda m: int(m['role'].split(' - ')[0].split(':')[0]))
                        
                        # 당직표 모드에서는 기본적으로 연락처도 함께 제공
                        schedule_info = []
                        for m in matching_schedules:
                            phone_info = f" (연락처: {m['phone']})" if m.get('phone') else ""
                            schedule_info.append(f"• {format_work_schedule(m['role'])}: {m['name']}{phone_info}")
                        
                        response_text = f"[{entities['date']}] {entities['department']} 당직표:\n\n" + "\n".join(schedule_info)
                        print(f"응답: {response_text}")
                        
                        response_time = (time.time() - start_time) * 1000
                        return create_chatbot_response_with_logging(
                            response_text=response_text,
                            session_id=session_id,
                            message=message,
                            response_time=response_time,
                            client_ip=client_ip,
                            entities=entities
                        )
                    
                    # 최적의 결과 찾기
                    best_match = None
                    exact_match = False
                    
                    # 정확한 부서 일치 결과 찾기
                    if 'department' in entities:
                        target_dept = entities['department']
                        print(f"부서 일치 검색: '{target_dept}'")
                        
                        # 먼저 부서와 날짜가 모두 일치하는 항목 찾기
                        for result in search_results:
                            metadata = result["entity"]
                            if metadata.get('department') == target_dept:
                                if 'date' in entities and metadata.get('date') == entities['date']:
                                    best_match = metadata
                                    exact_match = True
                                    print(f"  부서+날짜 일치 항목 발견: {metadata}")
                                    break
                        
                        # 부서만 일치하는 항목 찾기 (날짜 일치 항목이 없는 경우)
                        if not exact_match:
                            for result in search_results:
                                metadata = result["entity"]
                                if metadata.get('department') == target_dept:
                                    best_match = metadata
                                    exact_match = True
                                    print(f"  부서 일치 항목 발견: {metadata}")
                                    break
                    
                    # 정확한 일치 항목이 없으면 DB에서 조회 시도
                    if not exact_match and 'department' in entities:
                        print("정확한 일치 항목이 없어 DB에서 직접 조회합니다.")
                        # 날짜가 없으면 오늘 날짜 사용
                        date_str = entities.get("date") or datetime.now().strftime('%Y-%m-%d')
                        dept_name = entities.get("department")
                        role_name = entities.get("role")
                        time_range = entities.get("time_range")
                        night_shift = entities.get("night_shift", False)
                        specific_hour = entities.get("specific_hour")
                        
                        # 특정 시간이 없으면 현재 시간 사용
                        if specific_hour is None and 'current_hour' in entities:
                            specific_hour = entities['current_hour']
                        
                        schedule = await get_schedule_from_db_async(date_str, dept_name, role_name, time_range, night_shift, specific_hour)
                        
                        if schedule:
                            print(f"DB 직접 조회 성공: {schedule.date} - {schedule.doctor.name}")
                            
                            # 현재 시간에 맞는 당직의인지 확인
                            current_time_match = False
                            if specific_hour is not None:
                                try:
                                    times = str(schedule.work_schedule).split(' - ')
                                    if len(times) == 2:
                                        start_hour = int(times[0].split(':')[0])
                                        end_hour = int(times[1].split(':')[0])
                                        
                                        # 시작 시간이 종료 시간과 같거나 더 클 경우 익일로 처리
                                        if end_hour <= start_hour:
                                            end_hour += 24
                                        
                                        # specific_hour 정규화 (익일 새벽 시간 처리)
                                        specific_hour_normalized = specific_hour
                                        if specific_hour < 12 and start_hour > 12:
                                            specific_hour_normalized = specific_hour + 24
                                            
                                        current_time_match = start_hour <= specific_hour_normalized < end_hour
                                except:
                                    current_time_match = True  # 파싱 실패 시 기본값
                            
                            if current_time_match or specific_hour is None:
                                # 당직의 정보 질문에는 기본적으로 연락처도 함께 제공
                                phone_info = f" (연락처: {schedule.doctor.phone_number})" if schedule.doctor.phone_number else ""
                                response_text = f"[{date_str}] {dept_name} {str(schedule.work_schedule)}는 {schedule.doctor.name}입니다.{phone_info}"
                                
                                print(f"응답: {response_text}")
                                response_time = (time.time() - start_time) * 1000
                                return create_chatbot_response_with_logging(
                                    response_text=response_text,
                                    session_id=session_id,
                                    message=message,
                                    response_time=response_time,
                                    client_ip=client_ip,
                                    entities=entities
                                )
                            else:
                                # 현재 시간에 해당하는 당직의가 없음
                                response_text = f"현재 시간({specific_hour}시)에는 {dept_name}의 당직 의사가 없습니다."
                                print(f"응답: {response_text}")
                                
                                response_time = (time.time() - start_time) * 1000
                                return create_chatbot_response_with_logging(
                                    response_text=response_text,
                                    session_id=session_id,
                                    message=message,
                                    response_time=response_time,
                                    client_ip=client_ip,
                                    entities=entities
                                )
                        else:
                            print(f"DB 조회 실패: {date_str}에 해당하는 스케줄이 없습니다.")
                            response_text = f"{dept_name}의 당직 정보를 찾을 수 없습니다."
                            print(f"응답: {response_text}")
                            
                            response_time = (time.time() - start_time) * 1000
                            return create_chatbot_response_with_logging(
                                response_text=response_text,
                                session_id=session_id,
                                message=message,
                                response_time=response_time,
                                client_ip=client_ip,
                                entities=entities
                            )
                    
                    # 벡터 검색 결과 중 최선의 결과 선택
                    if not best_match and search_results:
                        # 유사도 기반 선택 (점수가 가장 높은 것)
                        best_match = search_results[0]["entity"]
                        print(f"유사도 기반 최적 결과 선택: {best_match}")
                    
                    if best_match:
                        # 결과가 실제 질문과 관련이 있는지 확인
                        if 'department' in entities and best_match.get('department') != entities['department']:
                            response_text = f"{entities['department']}의 당직 정보를 찾을 수 없습니다."
                        else:
                            # 당직의 정보 질문에는 기본적으로 연락처도 함께 제공
                            phone_info = f" (연락처: {best_match['phone']})" if best_match.get('phone') else ""
                            response_text = f"[{best_match['date']}] {best_match['department']} {format_work_schedule(best_match['role'])}는 {best_match['name']}입니다.{phone_info}"
                    else:
                        response_text = "죄송합니다. 질문에 맞는 당직 정보를 찾을 수 없습니다."
                        
                    response = response_text  # 기존 변수명 유지를 위해
                else:
                    print("벡터 검색 결과가 없습니다.")
                    
                    # Gemini RAG로 대체 시도
                    try:
                        print("벡터 검색 결과가 없어, Gemini RAG로 대체 시도합니다...")
                        rag_request = RAGRequest(query=message, max_results=10)
                        rag_response = await rag_query(rag_request)
                        
                        response_time = (time.time() - start_time) * 1000
                        
                        if rag_response.get("status") == "success" and "answer" in rag_response:
                            return create_chatbot_response_with_logging(
                                response_text=rag_response["answer"],
                                session_id=session_id,
                                message=message,
                                response_time=response_time,
                                client_ip=client_ip,
                                entities={'fallback_to_rag': True}
                            )
                        else:
                            response_text = "죄송합니다. 질문에 맞는 정보를 찾을 수 없습니다. 다른 방식으로 질문해 주세요."
                    except Exception as rag_error:
                        print(f"Gemini RAG 대체 시도 오류: {rag_error}")
                        response_time = (time.time() - start_time) * 1000
                        response_text = "죄송합니다. 질문에 맞는 정보를 찾을 수 없습니다. 다른 방식으로 질문해 주세요."
                        
                    response = response_text  # 기존 변수명 유지를 위해
            except Exception as e:
                print(f"벡터 검색 오류: {e}")
                import traceback
                traceback.print_exc()
                
                # Gemini RAG로 대체 시도
                try:
                    print("벡터 검색 오류로 Gemini RAG로 대체 시도합니다...")
                    rag_request = RAGRequest(query=message, max_results=10)
                    rag_response = await rag_query(rag_request)
                    
                    response_time = (time.time() - start_time) * 1000
                    
                    if rag_response.get("status") == "success" and "answer" in rag_response:
                        return create_chatbot_response_with_logging(
                            response_text=rag_response["answer"],
                            session_id=session_id,
                            message=message,
                            response_time=response_time,
                            client_ip=client_ip,
                            entities={'vector_search_error': True, 'fallback_to_rag': True}
                        )
                    else:
                        response_text = f"검색 중 오류가 발생했습니다: {str(e)}"
                except Exception as rag_error:
                    print(f"Gemini RAG 대체 시도 오류: {rag_error}")
                    response_time = (time.time() - start_time) * 1000
                    response_text = f"검색 중 오류가 발생했습니다: {str(e)}"
                    
                response = response_text  # 기존 변수명 유지를 위해
        else:
            print("❌ 벡터 스토어가 None입니다!")
            print("   서버 시작 시 벡터 스토어 초기화에 실패했을 가능성이 있습니다.")
            print("   FAISS, SentenceTransformer 등의 라이브러리 문제일 수 있습니다.")
            
            # 벡터 스토어가 없는 경우 Gemini RAG로 대체 시도
            try:
                print("벡터 스토어가 없어 Gemini RAG로 대체 시도합니다...")
                rag_request = RAGRequest(query=message, max_results=10)
                rag_response = await rag_query(rag_request)
                
                response_time = (time.time() - start_time) * 1000
                
                if rag_response.get("status") == "success" and "answer" in rag_response:
                    return create_chatbot_response_with_logging(
                        response_text=rag_response["answer"],
                        session_id=session_id,
                        message=message,
                        response_time=response_time,
                        client_ip=client_ip,
                        entities={'vector_store_unavailable': True, 'fallback_to_rag': True}
                    )
                else:
                    response_text = "벡터 검색 엔진이 준비되지 않았습니다."
            except Exception as rag_error:
                print(f"Gemini RAG 대체 시도 오류: {rag_error}")
                response_time = (time.time() - start_time) * 1000
                response_text = "벡터 검색 엔진이 준비되지 않았습니다."
                
            response = response_text  # 기존 변수명 유지를 위해
        
        print(f"응답: {response}")
        
        # 응답 시간 계산 및 로깅
        response_time = (time.time() - start_time) * 1000  # ms 단위
        return create_chatbot_response_with_logging(
            response_text=response, 
            session_id=session_id,
            message=message, 
            response_time=response_time,
            client_ip=client_ip,
            entities=entities if 'entities' in locals() else None
        )
        
    except Exception as e:
        # 전체 예외 처리
        print(f"Chat 엔드포인트 오류: {e}")
        import traceback
        traceback.print_exc()
        
        response_time = (time.time() - start_time) * 1000
        error_response = f"요청 처리 중 오류가 발생했습니다: {str(e)}"
        
        # 최후의 수단으로 Gemini RAG 시도
        try:
            print("전체 예외 발생, 마지막으로 Gemini RAG 시도...")
            rag_request = RAGRequest(query=req.message, max_results=10)
            rag_response = await rag_query(rag_request)
            
            if rag_response.get("status") == "success" and "answer" in rag_response:
                return create_chatbot_response_with_logging(
                    response_text=rag_response["answer"],
                    session_id=session_id,
                    message=req.message,
                    response_time=response_time,
                    client_ip=client_ip,
                    entities={'error': True}
                )
        except Exception:
            pass
        
        # 에러 응답도 로깅
        return create_chatbot_response_with_logging(
            response_text=error_response,
            session_id=session_id,
            message=req.message,
            response_time=response_time,
            client_ip=client_ip,
            entities={'error': True}
        )

# Django ORM 호출을 위한 동기 함수
def get_all_departments():
    """부서 목록을 가져오는 동기 함수"""
    return [dept.name for dept in Department.objects.all()]

# 동기 함수를 비동기로 변환
get_all_departments_async = sync_to_async(get_all_departments)

def generate_department_aliases(departments):
    """DB 부서명을 분석하여 동적으로 별칭 매핑 생성"""
    aliases = {}
    
    for dept in departments:
        # 응급 관련 매핑
        if '응급의학과' in dept:
            aliases['응급실'] = dept
            aliases['ER'] = dept
            aliases['응급과'] = dept
        
        # 소아과 응급실 매핑
        if '소아과 ER' in dept:
            aliases['소아과 응급실'] = dept
            aliases['소아 응급실'] = dept
        
        # 중환자실 매핑
        if '중환자실' in dept:
            if '내과계' in dept:
                aliases['내과 중환자실'] = dept
                aliases['내과 ICU'] = dept
            elif '외과계' in dept:
                aliases['외과 중환자실'] = dept
                aliases['외과 ICU'] = dept
            else:
                aliases['중환자실'] = dept
                aliases['ICU'] = dept
        
        # 병동 매핑
        if '병동' in dept:
            base_dept = dept.replace(' 병동', '')
            aliases[f'{base_dept}병동'] = dept
        
        # 외과 관련 매핑 (정확한 매칭을 위해 조건 수정)
        if dept == '외과 당직의':
            aliases['외과 당직'] = dept
        if dept == '외과 수술의':
            aliases['외과 수술'] = dept
            aliases['수술실'] = dept
        if '외과(ER call only)' in dept:
            aliases['외과 응급실'] = dept
            aliases['외과 ER'] = dept
        
        # NICU 매핑
        if 'NICU' in dept:
            aliases['신생아중환자실'] = dept
            aliases['신생아 중환자실'] = dept
    
    print(f"동적 생성된 부서 별칭: {aliases}")
    return aliases

# 동기 함수를 비동기로 변환
generate_department_aliases_async = sync_to_async(generate_department_aliases)

async def suggest_related_departments(message: str, input_dept_name: str = None):
    """부서 매칭 실패 시 관련 부서를 추천하는 함수"""
    print(f"===== 관련 부서 추천 시작 =====")
    print(f"     입력 메시지: '{message}'")
    print(f"     입력 부서명: '{input_dept_name}'")
    
    try:
        departments = await get_all_departments_async()
        sorted_departments = sorted(departments, key=len, reverse=True)
        
        # 키워드 추출
        keywords = []
        common_dept_keywords = ['외과', '내과', '소아과', '산부인과', '신경과', '정형외과', '성형외과', 
                              '신경외과', '흉부외과', '비뇨의학과', '이비인후과', '마취통증의학과',
                              '응급의학과', '재활의학과', '순환기내과', '소화기내과', '내분비내과', 
                              '호흡기내과', '당직의', '수술의', '담당의', '병동', '중환자실']
        
        # 입력된 부서명에서 키워드 찾기 (우선)
        if input_dept_name:
            for keyword in common_dept_keywords:
                if keyword in input_dept_name and keyword not in keywords:
                    keywords.append(keyword)
        
        # 전체 메시지에서 키워드 찾기
        for keyword in common_dept_keywords:
            if keyword in message and keyword not in keywords:
                keywords.append(keyword)
        
        print(f"     추출된 키워드: {keywords}")
        
        # 키워드가 포함된 관련 부서 찾기
        related_departments = []
        if keywords:
            for dept in sorted_departments:
                for keyword in keywords:
                    if keyword in dept and dept not in related_departments:
                        related_departments.append(dept)
                        break
        
        print(f"     관련 부서 찾음: {related_departments}")
        
        if related_departments:
            # 관련 부서가 있으면 추천 메시지 생성
            dept_list = '\n'.join([f"• {dept}" for dept in related_departments[:5]])  # 상위 5개만
            suggested_msg = f"⚠️ 해당 부서를 찾을 수 없습니다.\n\n🔍 혹시 다음 부서 중 하나를 찾으시나요?\n\n{dept_list}\n\n💡 예제 질문: \"오늘 {related_departments[0]} 당직 누구야?\""
            return suggested_msg, {'suggested_departments': related_departments}
        else:
            # 관련 부서가 없으면 전체 부서 목록 제공
            dept_list = '\n'.join([f"• {dept}" for dept in sorted_departments[:10]])  # 상위 10개만
            fallback_msg = f"⚠️ 해당 부서를 찾을 수 없습니다.\n\n📋 현재 등록된 부서 목록:\n\n{dept_list}\n\n💡 정확한 부서명으로 다시 질문해주세요."
            return fallback_msg, {}
        
    except Exception as e:
        print(f"관련 부서 추천 중 오류: {e}")
        return "부서를 찾을 수 없습니다. 정확한 부서명으로 다시 질문해주세요.", {}

def format_work_schedule(work_schedule):
    """근무 시간을 포맷팅하여 자정 넘어가는 경우 '익일' 표시"""
    try:
        work_schedule_str = str(work_schedule)
        
        if " - " in work_schedule_str:
            start_time, end_time = work_schedule_str.split(" - ")
            start_hour = int(start_time.split(":")[0])
            end_hour = int(end_time.split(":")[0])
            
            # 종료 시간이 시작 시간보다 작거나 같으면 익일로 처리
            if end_hour <= start_hour:
                return f"{start_time} - 익일 {end_time}"
            else:
                return work_schedule_str
        else:
            return work_schedule_str
    except Exception as e:
        print(f"근무 시간 포맷팅 오류: {e}")
        return str(work_schedule)

def extract_dept_keywords(message: str):
    """메시지에서 부서 관련 키워드 추출 - 구체적인 키워드 우선"""
    user_keywords = []
    
    # 구체적인 키워드를 먼저 확인 (길이가 긴 것부터)
    specific_keywords = [
        "심장혈관외과", "소화기내과", "순환기내과", "내분비내과", "호흡기내과",
        "마취통증의학과", "재활의학과", "응급의학과", "비뇨의학과", "이비인후과",
        "신경외과", "정형외과", "성형외과", "폐식도외과", 
        "소아과", "산부인과", "신경과", "내과", "외과"
    ]
    
    # 일반적인 키워드
    general_keywords = [
        "심장", "혈관", "폐", "식도", "흉부", "가슴", "뇌", "신경", "정형", 
        "재활", "성형", "비뇨", "이비인후", "마취", "통증", "응급", "중환자실",
        "병동", "NICU", "ER", "당직", "수술", "온콜", "on call"
    ]
    
    # 1. 먼저 구체적인 키워드 확인 (더 구체적인 것 우선)
    for keyword in specific_keywords:
        if keyword in message:
            user_keywords.append(keyword)
            # 구체적인 키워드가 발견되면 해당 키워드에 포함된 일반 키워드는 제외
            if keyword == "심장혈관외과":
                # "심장혈관외과"가 있으면 "심장", "혈관", "외과"는 별도로 추가하지 않음
                break
            elif keyword.endswith("외과") and len(keyword) > 2:
                # 다른 "XXX외과"가 있으면 "외과"는 별도로 추가하지 않음
                general_keywords = [k for k in general_keywords if k != "외과"]
            elif keyword.endswith("내과") and len(keyword) > 2:
                # 다른 "XXX내과"가 있으면 "내과"는 별도로 추가하지 않음  
                general_keywords = [k for k in general_keywords if k != "내과"]
    
    # 2. 구체적인 의료 키워드가 없는 경우에만 일반 키워드 추가
    if not any(k.endswith(("과", "실", "센터")) for k in user_keywords):
        for keyword in general_keywords:
            if keyword in message and keyword not in user_keywords:
                user_keywords.append(keyword)
    
    return user_keywords

def create_chatbot_response_with_logging(response_text, session_id, message, response_time, client_ip, entities=None):
    """챗봇 응답 생성 및 로깅"""
    if entities is None:
        entities = {}
    
    # 응답에서 의사 이름 추출하여 맥락 업데이트
    if session_id in session_conversations:
        context = session_conversations[session_id]
        
        # 응답 텍스트에서 의사 이름 패턴 찾기 (모든 의사 추출)
        doctor_patterns = [
            r'는\s*([가-힣]{2,4})\s*(?:입니다|이다|임)\.?',  # "는 유수현입니다"
            r'([가-힣]{2,4})\s*(?:입니다|이다|임)\.?',  # "유수현입니다"
            r'당직의?\s*(?:\([^)]*\))?\s*는\s*([가-힣]{2,4})',  # "당직의는 유수현" 또는 "당직의(연락처)는 유수현"
            r':?\s*([가-힣]{2,4})\s*\(',  # ": 유수현 ("
            r'([가-힣]{2,4})\s*의사의\s*연락처',  # "유수현 의사의 연락처"
        ]
        
        # 모든 의사 이름 추출
        found_doctors = []
        common_words = ['순환기내과', '응급의학과', '신경과', '외과', '내과', '소화기내과', '정형외과', '산부인과', '소아과', '당직', '병동', '담당', '오늘', '내일', '모레', '알려', '정보', '연락처', '시간', '당직표', '의사의', '선생의', '박사의']
        
        for pattern in doctor_patterns:
            matches = re.finditer(pattern, response_text)
            for match in matches:
                potential_name = match.group(1)
                # PA는 제외하고, 일반적인 단어가 아닌 경우만 의사 이름으로 인식
                if potential_name not in common_words and potential_name != 'PA':
                    if potential_name not in found_doctors:
                        found_doctors.append(potential_name)
                        print(f"===== 응답에서 의사 이름 감지: {potential_name} (패턴: {pattern}) =====")
        
        # entities에 의사 정보 추가
        if found_doctors:
            if len(found_doctors) == 1:
                if not entities.get('doctor_name'):
                    entities['doctor_name'] = found_doctors[0]
            else:
                entities['doctor_names'] = found_doctors
                if not entities.get('doctor_name'):
                    entities['doctor_name'] = found_doctors[0]  # 호환성 유지
        
        # 세션 맥락 업데이트
        print(f"===== 세션 맥락 업데이트 시작 =====")
        print(f"     session_id: {session_id}")
        print(f"     entities: {entities}")
        print(f"     message: {message}")
        print(f"     response_text: {response_text[:100]}...")
        
        print(f"===== 업데이트 전 맥락 상태 =====")
        print(f"     이전 last_department: {context.last_department}")
        print(f"     이전 last_role: {context.last_role}")
        print(f"     이전 last_date: {context.last_date}")
        print(f"     이전 last_doctor: {context.last_doctor}")
        print(f"     이전 last_doctors: {context.last_doctors}")
        
        context.update_context(entities or {}, message, response_text)
        
        print(f"===== 업데이트 후 맥락 상태 =====")
        print(f"     새로운 last_department: {context.last_department}")
        print(f"     새로운 last_role: {context.last_role}")
        print(f"     새로운 last_date: {context.last_date}")
        print(f"     새로운 last_doctor: {context.last_doctor}")
        print(f"     새로운 last_doctors: {context.last_doctors}")
        print(f"     대화 기록 수: {len(context.conversation_history)}")
        
        print(f"✅ 세션 맥락 업데이트 완료: {context.get_context_info()}")
    else:
        print(f"⚠️ 세션 맥락을 찾을 수 없음: {session_id}")
    
    # 응답은 반드시 반환 (로깅 실패와 무관하게)
    response_obj = {"answer": response_text}
    
    # 로깅 시도 (여러 방법으로)
    logging_attempts = []
    
    try:
        # 1. 정식 로깅 함수 시도
        log_chatbot_conversation(
            session_id=session_id,
            user_message=message,
            bot_response=response_text,
            response_time=response_time,
            ip_address=client_ip,
            entities=entities
        )
        logging_attempts.append("정식 로깅 성공")
        
        if LOGGING_ENABLED:
            print(f"✅ 챗봇 대화가 정식 로그 시스템에 저장되었습니다.")
        else:
            print(f"📝 챗봇 대화가 기본 로그 시스템에 저장되었습니다.")
            
    except Exception as primary_error:
        print(f"⚠️ 정식 로깅 오류: {primary_error}")
        logging_attempts.append(f"정식 로깅 실패: {primary_error}")
        
        # 2. 직접 파일 로깅 시도
        try:
            import os
            from datetime import datetime
            
            log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "fastapi", "chatbot")
            os.makedirs(log_dir, exist_ok=True)
            
            today = datetime.now().strftime('%Y-%m-%d')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            backup_log_file = os.path.join(log_dir, f"direct_backup_{today}.txt")
            
            log_content = f"[{timestamp}] DIRECT_BACKUP | SESSION:{session_id} | USER:{message} | BOT:{response_text} | TIME:{response_time:.2f}ms | IP:{client_ip or 'unknown'} | ENTITIES:{entities or {}}\n"
            
            with open(backup_log_file, 'a', encoding='utf-8') as f:
                f.write(log_content)
                
            print(f"✅ 직접 백업 로깅 성공: {backup_log_file}")
            logging_attempts.append("직접 백업 로깅 성공")
            
        except Exception as backup_error:
            print(f"⚠️ 직접 백업 로깅도 실패: {backup_error}")
            logging_attempts.append(f"직접 백업 실패: {backup_error}")
            
            # 3. 최후의 수단 - 프로젝트 루트에 기록
            try:
                import os
                from datetime import datetime
                
                root_dir = os.path.dirname(__file__)
                emergency_file = os.path.join(root_dir, f"emergency_chatbot_log_{datetime.now().strftime('%Y%m%d')}.txt")
                
                emergency_content = f"[EMERGENCY {datetime.now().isoformat()}] {session_id}: {message} -> {response_text} ({response_time:.2f}ms)\n"
                
                with open(emergency_file, 'a', encoding='utf-8') as f:
                    f.write(emergency_content)
                    
                print(f"🚨 응급 로깅 성공: {emergency_file}")
                logging_attempts.append("응급 로깅 성공")
                
            except Exception as emergency_error:
                print(f"💀 응급 로깅도 실패: {emergency_error}")
                logging_attempts.append(f"응급 로깅 실패: {emergency_error}")
    
    # 로깅 결과 출력 (디버깅용)
    print(f"📋 로깅 시도 결과: {len(logging_attempts)}개 시도")
    for i, attempt in enumerate(logging_attempts, 1):
        print(f"   {i}. {attempt}")
    
    # 최소한의 콘솔 로깅은 항상 수행
    print(f"💬 대화 요약: 세션={session_id[:8]}... | 질문={message[:30]}... | 응답={response_text[:30]}... | {response_time:.0f}ms")
    
    return response_obj

async def extract_entities(message: str):
    """사용자 메시지에서 주요 엔티티 추출"""
    entities = {}
    
    # n시간 뒤/후 표현 처리
    hours_later_pattern = re.search(r'(\d+)시간\s*(?:뒤|후)', message)
    if hours_later_pattern:
        hours = int(hours_later_pattern.group(1))
        future_time = datetime.now() + timedelta(hours=hours)
        entities["specific_hour"] = future_time.hour
        entities["date"] = future_time.strftime('%Y-%m-%d')
        print(f"n시간 뒤 표현 감지: {hours}시간 후 -> {future_time.strftime('%Y-%m-%d %H시')}")
    
    # 구체적인 시간 추출 (HH시, H시, 오전/오후 H시 등) - 날짜 전에 시간 추출
    time_pattern = re.search(r'(\d{1,2})(?:시|:00|:30|시\s?(?:반|정각)?)', message)
    if time_pattern and "specific_hour" not in entities:  # n시간 뒤 표현이 없을 때만 처리
        hour = int(time_pattern.group(1))
        # 12시간제 처리 (오후 2시 → 14시)
        if '오후' in message and hour < 12:
            hour += 12
        elif '아침' in message and hour >= 12:
            hour = hour % 12
        
        # 시간을 24시간제로 저장
        entities["specific_hour"] = hour
        print(f"특정 시간 추출됨: {hour}시")
    
    # '지금' 키워드가 있으면 현재 날짜 자동 추가
    if "지금" in message or "현재" in message:
        today = datetime.now()
        entities["date"] = today.strftime('%Y-%m-%d')
        print(f"'지금/현재' 키워드 감지 - 현재 날짜 추가: {entities['date']} (현재 시간: {today.strftime('%Y-%m-%d %H:%M:%S')})")
    
    # 날짜 추출 - 시간 추출 후에 처리
    date = parse_date_reference(message)
    if date:
        entities["date"] = date
        
        # 새벽 시간대(0-8시)이고 '어제' 키워드가 없는 경우에 날짜 조정
        if "specific_hour" in entities and 0 <= entities["specific_hour"] < 8 and "어제" not in message:
            # 날짜 객체로 변환
            original_date = datetime.strptime(entities["date"], '%Y-%m-%d')
            # 이전 날짜로 설정
            adjusted_date = original_date - timedelta(days=1)
            entities["date"] = adjusted_date.strftime('%Y-%m-%d')
            print(f"새벽 시간대로 날짜 조정: {entities['date']}")
    
    # 날짜 묻는 질문인지 확인
    if re.search(r"(오늘|지금).*(날짜|몇월\s*몇일)", message):
        entities["date_question"] = True
    
    # 부서 추출 (Django DB에서 부서명 가져오기) - 부서 연락처 질문과 동일한 로직 사용
    departments = await get_all_departments_async()
    print(f"===== extract_entities 부서 추출 시작 =====")
    print(f"     메시지: '{message}'")
    print(f"     전체 부서 수: {len(departments)}개")
    
    # 동적 별칭 매핑 생성
    department_aliases = await generate_department_aliases_async(departments)
    
    # 부서명을 길이 기준으로 내림차순 정렬 (더 구체적인 부서명 우선)
    sorted_depts = sorted(departments, key=len, reverse=True)
    print(f"     길이순 정렬된 부서 목록 (상위 10개): {sorted_depts[:10]}")
    
    matched_dept = None
    
    # 0. 별칭 매핑 먼저 확인 (정확한 단어 매칭)
    for alias, official_name in department_aliases.items():
        # 단어 경계를 고려한 정확한 매칭
        pattern = r'\b' + re.escape(alias) + r'\b'
        if re.search(pattern, message):
            matched_dept = official_name
            print(f"     ✅ 부서 별칭 매핑: '{alias}' → '{official_name}'")
            break
    
    # 1. 전체 메시지에서 부서명 매칭 - 모든 매칭을 찾아서 가장 적합한 것 선택 (별칭 매핑이 없는 경우만)
    if not matched_dept:
        print(f"     부서명 직접 매칭 시작 - 메시지: '{message}'")
        all_matches = []
        for dept in sorted_depts:
            if dept in message:
                all_matches.append(dept)
                print(f"     🔍 부서 매칭 후보: '{dept}'")
    
        if all_matches:
            # 가장 적합한 부서명 선택: 1) 길이 우선, 2) 공백 없는 것 우선, 3) 메시지에서 먼저 나오는 것 우선
            def match_priority(dept):
                return (
                    len(dept),  # 길이 (길수록 좋음)
                    -dept.count(' '),  # 공백 개수 (적을수록 좋음, 음수로 역순)
                    -message.find(dept)  # 메시지에서 위치 (앞에 나올수록 좋음, 음수로 역순)
                )
            
            matched_dept = max(all_matches, key=match_priority)
            print(f"     ✅ 일반 엔티티에서 부서 매칭 (최적): '{matched_dept}' (후보: {all_matches})")
            
            # 우선순위 점수 디버깅
            for dept in all_matches:
                priority = match_priority(dept)
                print(f"       - '{dept}': 우선순위 점수 = {priority} (길이={len(dept)}, 공백={dept.count(' ')}, 위치={message.find(dept)})")
    
    # 2. 부분 매칭 (공백 제거 후 비교, 더 구체적인 것 우선)
    if not matched_dept:
        for dept in sorted_depts:
            if dept.replace(" ", "") in message.replace(" ", ""):
                matched_dept = dept
                print(f"     ✅ 일반 엔티티에서 부분 매칭: '{dept}' (공백 제거 후)")
                break
    
    # 3. 키워드 기반 매칭 (위의 방법으로 매칭되지 않은 경우)
    if not matched_dept:
        user_keywords = extract_dept_keywords(message)
        print(f"사용자 입력에서 추출된 키워드: {user_keywords}")
        
        if user_keywords:
                        # 키워드가 포함된 부서 찾기 (길이순 정렬된 부서에서)
            for dept in sorted_depts:
                for keyword in user_keywords:
                    if keyword in dept:
                        matched_dept = dept
                        print(f"     ✅ 일반 엔티티에서 키워드 매칭: '{dept}' (키워드: {keyword})")
                        break
                if matched_dept:
                    break
    
    if matched_dept:
        entities["department"] = matched_dept
        print(f"부서 매칭 완료: '{matched_dept}'")
    else:
        # 부서명이 매칭되지 않은 경우 찾지 못한 부서명 기록
        dept_keywords = ["과", "부서", "센터", "클리닉", "실"]
        query_dept_for_recommendation = None
        
        for keyword in dept_keywords:
            if keyword in message:
                # 부서명 같은 단어가 있지만 매칭되지 않음
                entities["unmatched_department"] = True
                
                # 추천을 위해 사용자가 입력한 부서명 추출
                words = message.split()
                for word in words:
                    if keyword in word:
                        query_dept_for_recommendation = word
                        break
                
                print(f"부서 관련 키워드 감지되었으나 매칭되지 않음: '{message}' (추출된 부서명: {query_dept_for_recommendation})")
                break
        
        # 일반적인 의료 키워드도 확인
        if not query_dept_for_recommendation:
            medical_keywords = ['외과', '내과', '소아', '정신', '피부', '안과', '이비인후과', 
                              '산부인과', '비뇨기과', '응급', '중환자', '재활', '마취', '영상', '병리']
            for keyword in medical_keywords:
                if keyword in message:
                    query_dept_for_recommendation = keyword
                    entities["unmatched_department"] = True
                    print(f"의료 키워드 감지되었으나 매칭되지 않음: '{message}' (추출된 키워드: {keyword})")
                    break
        
        # 추천용 부서명 저장
        if query_dept_for_recommendation:
            entities["query_dept"] = query_dept_for_recommendation
    
    # 현재 날짜를 기본값으로 설정 (부서가 매칭되었지만 날짜가 없는 경우)
    if matched_dept and "date" not in entities:
        entities["date"] = datetime.now().strftime('%Y-%m-%d')
        print(f"부서가 매칭되었으므로 현재 날짜 자동 추가: {entities['date']}")
    
    # 시간대 추출 (아침, 오전, 오후, 저녁, 야간 등)
    time_keywords = {
        '아침': '08:00 - 12:00',
        '오전': '08:00 - 12:00',
        '점심': '12:00 - 14:00',
        '오후': '14:00 - 18:00',
        '저녁': '18:00 - 22:00',
        '야간': '22:00 - 08:00',
        '새벽': '00:00 - 08:00'
    }
    
    for keyword, time_range in time_keywords.items():
        if keyword in message:
            entities["time_range"] = time_range
            break
    
    # 현재 시간 정보 추가
    current_hour = datetime.now().hour
    entities["current_hour"] = current_hour
    
    # 역할 추출을 개선 - 더 다양한 표현 처리
    role_keywords = {
        '당직': '당직의', 
        '당직의': '당직의',
        '당직의사': '당직의',
        '당직 의사': '당직의',
        '수술의': '수술의',
        '야간': '당직의',
        '야간 근무': '당직의', 
        '밤': '당직의',
        '밤 근무': '당직의',
        '오늘 담당': '당일담당의'
    }
    
    for key, value in role_keywords.items():
        if key in message:
            entities["role"] = value
            # 당직 관련 키워드가 있으면 현재 시간대도 고려
            if value == '당직의':
                now = datetime.now()
                # 저녁~아침 시간대인 경우 야간 당직 시간대 추가
                if now.hour >= 20 or now.hour < 8:
                    entities["night_shift"] = True
            break
    
    # '누구' 키워드 정교한 분류 - 시스템 질문 vs 의료진 질문 구분
    if 'role' not in entities and ('누구' in message or '담당' in message):
        # 시스템 관련 질문 패턴 체크
        system_patterns = [
            r'너는?\s*누구', r'당신은?\s*누구', r'너는?\s*뭐', r'당신은?\s*뭐',
            r'너의?\s*이름', r'당신의?\s*이름', r'자기소개', r'소개해',
            r'너는?\s*어떤', r'당신은?\s*어떤'
        ]
        
        is_system_question = any(re.search(pattern, message) for pattern in system_patterns)
        
        # 시스템 질문이 아닐 때만 담당의 역할 설정
        if not is_system_question:
            entities["role"] = '담당의'
    
    # 연락처 요청 여부
    if "번호" in message or "연락처" in message or "전화" in message or "폰" in message:
        entities["phone_requested"] = True
    
    print(f"===== extract_entities 최종 결과 =====")
    print(f"     추출된 엔티티: {entities}")
    
    return entities

# 의사 정보 조회 관련 함수들
async def get_doctor_info_async(doctor_name):
    """Django DB에서 의사 정보 조회 (비동기)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_doctor_info, doctor_name)

def get_doctor_info(doctor_name):
    """Django DB에서 의사 정보 조회"""
    print(f"===== 의사 정보 조회 시작 =====")
    print(f"     의사명: {doctor_name}")
    
    try:
        # Django 모델 사용하여 의사 정보 조회
        from schedule.models import Doctor
        
        # 정확한 이름 매치
        doctor = Doctor.objects.filter(name=doctor_name).first()
        
        if doctor:
            print(f"===== 의사 정보 발견 =====")
            print(f"     이름: {doctor.name}")
            print(f"     연락처: {doctor.phone_number}")
            print(f"     부서: {doctor.department.name if doctor.department else 'N/A'}")
            return doctor
        else:
            print(f"===== 의사 정보 없음: {doctor_name} =====")
            return None
            
    except Exception as e:
        print(f"의사 정보 조회 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_doctor_name_from_message(message: str):
    """메시지에서 의사 이름 추출"""
    print(f"===== 의사 이름 추출 시작 =====")
    print(f"     입력 메시지: '{message}'")
    
    # 부서명이나 일반적인 의료 용어 제외 목록
    excluded_terms = [
        '중환자실', '응급실', '수술실', '병동', '외래', '입원실',
        '내과', '외과', '정형외과', '신경외과', '흉부외과', '성형외과',
        '소아과', '산부인과', '정신과', '피부과', '안과', '이비인후과',
        '비뇨기과', '방사선과', '병리과', '마취과', '재활의학과',
        '응급의학과', '가정의학과', '예방의학과', '직업환경의학과',
        '순환기내과', '소화기내과', '호흡기내과', '신장내과',
        '내분비내과', '혈액종양내과', '감염내과', '류마티스내과',
        '당직의', '담당의', '주치의', '레지던트', '인턴', '수술의',
        '간호사', '간호부', '수간호사', '원장', '부원장'
    ]
    
    # "의사이름 의사/선생님/박사 연락처 알려줘" 패턴 (명확한 의사 호칭이 있는 경우)
    contact_pattern = re.search(r'([가-힣]{2,4})\s*(?:의사|선생님|박사)\s*(?:연락처|전화번호)\s*(?:알려줘|뭐야|는)', message)
    if contact_pattern:
        doctor_name = contact_pattern.group(1)
        if doctor_name not in excluded_terms:
            print(f"     ✅ 연락처 패턴에서 의사 이름 추출: '{doctor_name}'")
            return doctor_name
        else:
            print(f"     ❌ 제외 목록에 포함된 용어: '{doctor_name}'")
    
    # 단순히 한글 이름 + 연락처 패턴 (더 엄격한 조건 적용)
    simple_pattern = re.search(r'([가-힣]{2,3})\s*(?:연락처|전화번호)', message)
    if simple_pattern:
        doctor_name = simple_pattern.group(1)
        # 부서명이나 의료 용어가 아닌 경우에만 의사 이름으로 인식
        if doctor_name not in excluded_terms and len(doctor_name) <= 3:
            # 추가로 "부서 + 연락처" 패턴인지 확인
            if not re.search(rf'(?:과|실|센터|부서)\s*{doctor_name}\s*(?:연락처|전화번호)', message):
                print(f"     ✅ 단순 패턴에서 의사 이름 추출: '{doctor_name}'")
                return doctor_name
            else:
                print(f"     ❌ 부서 연락처 패턴으로 판단: '{doctor_name}'")
        else:
            print(f"     ❌ 제외 목록에 포함되거나 길이가 긴 용어: '{doctor_name}'")
    
    print(f"     ❌ 의사 이름 추출 실패")
    return None

def is_doctor_schedule_question(message: str):
    """개인별 의사 스케줄 질문인지 확인"""
    print(f"===== 개인별 스케줄 질문 확인 =====")
    print(f"     입력 메시지: '{message}'")
    
    # 스케줄 관련 키워드
    schedule_keywords = ['당직', '스케줄', '일정', '언제', '며칠', '몇일', '근무']
    
    # 의사 호칭 키워드  
    doctor_titles = ['교수', '교수님', '의사', '선생님']
    
    # 의사 이름 + 호칭 + 스케줄 키워드 패턴
    for title in doctor_titles:
        for keyword in schedule_keywords:
            # "조준환 교수님 당직 언제야?" 패턴
            pattern = rf'([가-힣]{{2,4}})\s*{title}(?:님)?\s*.*{keyword}'
            if re.search(pattern, message):
                print(f"     ✅ 개인별 스케줄 질문 감지: 패턴='{pattern}'")
                return True
    
    # "조준환 당직 언제야?" (호칭 없는 패턴) - 부서명 제외 강화
    for keyword in schedule_keywords:
        # 부서 패턴인지 먼저 확인 (XXX과 당직 형태)
        dept_pattern_check = re.search(r'[가-힣]+과\s+' + keyword, message)
        if dept_pattern_check:
            print(f"     ❌ 부서 패턴 감지: '{dept_pattern_check.group(0)}' - 개인 질문 아님")
            continue
        
        # 개인 이름 패턴: 공백 또는 문장 시작 후 2-4글자 한글 + 당직
        pattern = rf'(?:^|\s)([가-힣]{{2,4}})\s+{keyword}'
        match = re.search(pattern, message)
        if match:
            name_candidate = match.group(1)
            print(f"     패턴 매치: '{pattern}' → '{name_candidate}'")
            
            # 부서명 제외 리스트 확장
            dept_keywords = ['순환기내과', '순환기', '환기내과', '기내과', '외과', '내과', '정형외과', '소아과', '산부인과', 
                           '신경과', '신경외과', '응급의학과', '마취과', '재활의학과',
                           '중환자실', '응급실', '수술실', '병동', '당직의', '담당의', '수술의',
                           '소화기내과', '호흡기내과', '내분비내과', '혈액종양내과', '감염내과', '류마티스내과']
            
            if name_candidate not in dept_keywords:
                print(f"     ✅ 개인별 스케줄 질문 감지: 패턴='{pattern}', 이름='{name_candidate}'")
                return True
            else:
                print(f"     ❌ 부서명으로 판단: '{name_candidate}'")
    
    print(f"     ❌ 개인별 스케줄 질문 아님")
    return False

def extract_doctor_name_for_schedule(message: str):
    """스케줄 질문에서 의사 이름 추출"""
    print(f"===== 스케줄용 의사 이름 추출 시작 =====")
    print(f"     입력 메시지: '{message}'")
    
    # 의사 호칭 키워드
    doctor_titles = ['교수', '교수님', '의사', '선생님']
    
    # 스케줄 관련 키워드
    schedule_keywords = ['당직', '스케줄', '일정', '언제', '며칠', '몇일', '근무']
    
    # 패턴 1: "조준환 교수님 당직 언제야?" 
    for title in doctor_titles:
        for keyword in schedule_keywords:
            pattern = rf'([가-힣]{{2,4}})\s*{title}(?:님)?\s*.*{keyword}'
            match = re.search(pattern, message)
            if match:
                doctor_name = match.group(1)
                print(f"     ✅ 호칭 패턴에서 의사 이름 추출: '{doctor_name}' (패턴: {pattern})")
                return doctor_name
    
    # 패턴 2: "조준환 당직 언제야?" (호칭 없는 패턴) - 부서명 제외 강화
    for keyword in schedule_keywords:
        # 부서 패턴인지 먼저 확인 (XXX과 당직 형태)
        dept_pattern_check = re.search(r'[가-힣]+과\s+' + keyword, message)
        if dept_pattern_check:
            print(f"     ❌ 부서 패턴 감지: '{dept_pattern_check.group(0)}' - 개인 질문 아님")
            continue
        
        # 개인 이름 패턴: 공백 또는 문장 시작 후 2-4글자 한글 + 당직
        pattern = rf'(?:^|\s)([가-힣]{{2,4}})\s+{keyword}'
        match = re.search(pattern, message)
        if match:
            name_candidate = match.group(1)
            print(f"     패턴 매치: '{pattern}' → '{name_candidate}'")
            
            # 부서명 제외 리스트 확장
            dept_keywords = ['순환기내과', '순환기', '환기내과', '기내과', '외과', '내과', '정형외과', '소아과', '산부인과', 
                           '신경과', '신경외과', '응급의학과', '마취과', '재활의학과',
                           '중환자실', '응급실', '수술실', '병동', '당직의', '담당의', '수술의',
                           '소화기내과', '호흡기내과', '내분비내과', '혈액종양내과', '감염내과', '류마티스내과']
            
            if name_candidate not in dept_keywords:
                print(f"     ✅ 단순 패턴에서 의사 이름 추출: '{name_candidate}' (패턴: {pattern})")
                return name_candidate
            else:
                print(f"     ❌ 부서명으로 판단: '{name_candidate}'")
    
    print(f"     ❌ 스케줄용 의사 이름 추출 실패")
    return None

async def get_doctor_monthly_schedule_async(doctor_name, target_date=None):
    """의사의 당직 스케줄을 비동기로 조회 (특정 날짜/월 고려)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_doctor_monthly_schedule, doctor_name, target_date)

def get_doctor_monthly_schedule(doctor_name, target_date=None):
    """의사의 당직 스케줄 조회 (특정 날짜/월 고려)"""
    print(f"===== 의사 월간 스케줄 조회 시작 =====")
    print(f"     의사명: {doctor_name}")
    print(f"     목표 날짜: {target_date}")
    
    try:
        from schedule.models import Doctor, Schedule
        from datetime import datetime, timedelta
        
        # 의사 정보 조회
        doctor = Doctor.objects.filter(name=doctor_name).first()
        if not doctor:
            print(f"     ❌ 의사 정보 없음: {doctor_name}")
            return None
        
        print(f"     ✅ 의사 정보 발견: {doctor.name} ({doctor.department.name if doctor.department else 'N/A'})")
        
        # 목표 월 계산
        if target_date:
            # 목표 날짜가 주어진 경우 해당 날짜의 월을 사용
            target_datetime = datetime.strptime(target_date, '%Y-%m-%d')
            target_year = target_datetime.year
            target_month = target_datetime.month
        else:
            # 목표 날짜가 없으면 현재 월 사용
            today = datetime.now()
            target_year = today.year
            target_month = today.month
        
        # 목표 월의 첫날과 마지막날 계산
        first_day = datetime(target_year, target_month, 1).date()
        
        # 다음 달의 첫날에서 하루 빼면 해당 달의 마지막날
        if target_month == 12:
            next_month = datetime(target_year + 1, 1, 1).date()
        else:
            next_month = datetime(target_year, target_month + 1, 1).date()
        last_day = next_month - timedelta(days=1)
        
        print(f"     조회 기간: {first_day} ~ {last_day}")
        
        # 해당 의사의 현재 달 스케줄 조회
        schedules = Schedule.objects.filter(
            doctor=doctor,
            date__gte=first_day,
            date__lte=last_day
        ).select_related('work_schedule').order_by('date')
        
        schedule_list = list(schedules)
        print(f"     ✅ 스케줄 발견: {len(schedule_list)}개")
        
        if schedule_list:
            for schedule in schedule_list:
                print(f"       - {schedule.date}: {schedule.work_schedule}")
        
        return {
            'doctor': doctor,
            'schedules': schedule_list,
            'period': f"{target_year}년 {target_month}월",
            'total_count': len(schedule_list),
            'target_year': target_year,
            'target_month': target_month
        }
        
    except Exception as e:
        print(f"월간 스케줄 조회 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return None

def format_doctor_monthly_schedule(schedule_data):
    """의사 월간 스케줄을 포맷팅하여 응답 텍스트 생성"""
    if not schedule_data or not schedule_data['schedules']:
        doctor_name = schedule_data['doctor'].name if schedule_data and schedule_data['doctor'] else "해당 의사"
        period = schedule_data['period'] if schedule_data else "이번 달"
        return f"{doctor_name} 의사의 {period} 당직 스케줄이 없습니다."
    
    doctor = schedule_data['doctor']
    schedules = schedule_data['schedules']
    period = schedule_data['period']
    total_count = schedule_data['total_count']
    
    # 응답 헤더
    response_lines = [
        f"👨‍⚕️ {doctor.name} 의사 {period} 당직 스케줄",
        f"🏥 소속: {doctor.department.name if doctor.department else 'N/A'}",
        f"📞 연락처: {doctor.phone_number if doctor.phone_number else '정보 없음'}",
        f"📅 총 당직 일수: {total_count}일",
        "",
        "📋 상세 스케줄:"
    ]
    
    # 스케줄 목록
    for schedule in schedules:
        date_str = schedule.date.strftime('%m월 %d일 (%a)')
        work_time = format_work_schedule(str(schedule.work_schedule))
        response_lines.append(f"• {date_str}: {work_time}")
    
    return "\n".join(response_lines)

# FastAPI 서버 실행 (개발용)
if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("🔥 FastAPI 챗봇 서버를 시작합니다...")
    print("="*60)
    
    # 시스템 상태 체크
    print("📋 시스템 상태 체크:")
    print(f"   ✅ Django 설정: {'완료' if 'django' in sys.modules else '실패'}")
    print(f"   ✅ 현재 경로: {os.getcwd()}")
    
    print("\n🌐 서버 정보:")
    print("   🔗 FastAPI 서버: http://localhost:8080")  
    print("   📚 API 문서: http://localhost:8080/docs")
    print("   💬 React 프론트엔드: http://localhost:3000")
    print("   📁 로그 위치: logs/fastapi/chatbot/")
    print("   ⛔ 서버 종료: Ctrl+C")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")

