from fastapi import FastAPI, Request, Depends # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from pydantic import BaseModel # type: ignore
import json
import os
import sqlite3
from datetime import datetime, timedelta
import re
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

# Django 프로젝트 루트 경로를 Python 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oncall_system.settings")

# Django 설정 초기화
import django # type: ignore
django.setup()

# Django 모델 가져오기
from schedule.models import Schedule, Doctor, Department, WorkSchedule

# 현재 시스템 시간 출력 (디버깅용)
current_time = datetime.now()
print(f"===== 시스템 현재 시간: {current_time} =====")

app = FastAPI()

# 정적 파일 디렉토리 설정
static_dir = Path(__file__).parent / "static"
if not static_dir.exists():
    static_dir.mkdir(parents=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 벡터 검색 설정
VECTOR_DB_PATH = "./vector_db.pkl"  # 벡터 및 메타데이터 저장 파일
VECTOR_DIM = 384  # SentenceTransformer 모델 출력 차원

# SentenceTransformer 모델 로드
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# FAISS 인덱스 초기화 또는 로드
class FAISSVectorStore:
    def __init__(self, vector_dim):
        self.vector_dim = vector_dim
        self.index = None
        self.metadata = []  # 각 벡터에 대한 메타데이터 저장
        self.load_or_create_index()
    
    def load_or_create_index(self):
        """저장된 인덱스를 로드하거나 새로운 인덱스 생성"""
        if os.path.exists(VECTOR_DB_PATH):
            try:
                with open(VECTOR_DB_PATH, 'rb') as f:
                    data = pickle.load(f)
                    self.index = data['index']
                    self.metadata = data['metadata']
                print(f"기존 벡터 데이터베이스를 로드했습니다. 벡터 수: {len(self.metadata)}")
                return
            except Exception as e:
                print(f"벡터 데이터베이스 로드 오류: {e}")
        
        # 새로운 인덱스 생성
        self.index = faiss.IndexFlatIP(self.vector_dim)  # 내적(코사인 유사도) 사용
        self.metadata = []
        print("새로운 벡터 데이터베이스를 생성했습니다.")
    
    def save_index(self):
        """인덱스를 파일로 저장"""
        with open(VECTOR_DB_PATH, 'wb') as f:
            pickle.dump({'index': self.index, 'metadata': self.metadata}, f)
        print(f"벡터 데이터베이스를 저장했습니다. 벡터 수: {len(self.metadata)}")
    
    def add_vectors(self, vectors, metadata_list):
        """벡터와 메타데이터 추가"""
        if len(vectors) == 0:
            return
        
        # 벡터를 numpy 배열로 변환
        vectors_np = np.array(vectors).astype('float32')
        
        # 기존 인덱스 삭제하고 새로 생성
        self.index = faiss.IndexFlatIP(self.vector_dim)
        self.metadata = metadata_list
        
        # 벡터 추가
        self.index.add(vectors_np)
        self.save_index()
        print(f"{len(vectors)}개의 벡터를 추가했습니다.")
    
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
try:
    vector_store = FAISSVectorStore(VECTOR_DIM)
    print("임베디드 벡터 검색 엔진이 준비되었습니다.")
except Exception as e:
    print(f"벡터 검색 초기화 오류: {e}")
    vector_store = None

# Django DB에서 데이터를 가져와 벡터 DB에 추가하는 함수
def update_vector_db_from_django_sync():
    """Django DB에서 당직 스케줄 데이터를 가져와 임베디드 벡터 DB에 추가 (동기 함수)"""
    try:
        if vector_store is None:
            print("벡터 DB가 초기화되지 않았습니다. 업데이트를 건너뜁니다.")
            return {"status": "error", "message": "벡터 DB가 초기화되지 않았습니다. 기능을 사용할 수 없습니다."}
            
        # 데이터 초기화
        vectors = []
        metadata_list = []
        
        # 오늘부터 모든 미래 스케줄 조회
        today = datetime.now().date()
        
        print(f"===== 벡터 DB 업데이트 시작: 현재 날짜 {today} =====")
        
        # Django 모델에서 모든 스케줄 데이터 가져오기 (미래 날짜 제한 없음)
        schedules = Schedule.objects.all().select_related('doctor', 'doctor__department', 'work_schedule')
        
        print(f"Django DB에서 총 {len(schedules)}개의 스케줄을 가져왔습니다.")
        
        # 모든 스케줄 데이터를 로그로 출력
        print(f"모든 스케줄 정보:")
        for i, schedule in enumerate(schedules):
            print(f"  {i+1}. {schedule.date} - {schedule.doctor.department.name} - {schedule.work_schedule} - {schedule.doctor.name}")
        
        # 날짜별 스케줄 카운트
        date_counts = {}
        for schedule in schedules:
            date_str = schedule.date.strftime('%Y-%m-%d')
            if date_str in date_counts:
                date_counts[date_str] += 1
            else:
                date_counts[date_str] = 1
        
        # 날짜별 스케줄 수 출력
        print("날짜별 스케줄 수:")
        for date_str, count in sorted(date_counts.items()):
            print(f"  {date_str}: {count}개")
        
        # 데이터가 없으면 경고 메시지 반환
        if len(schedules) == 0:
            print("주의: 스케줄 데이터가 없습니다. 챗봇 응답이 제한될 수 있습니다.")
            return {"status": "warning", "message": "스케줄 데이터가 없습니다. 관리자 페이지에서 일정을 추가해주세요."}
        
        # 스케줄 데이터를 문서 형태로 변환
        for count, schedule in enumerate(schedules):
            date_str = schedule.date.strftime('%Y-%m-%d')
            dept_name = schedule.doctor.department.name
            role_name = str(schedule.work_schedule)
            doctor_name = schedule.doctor.name
            phone_number = schedule.doctor.phone_number
            
            # 문서 텍스트 생성
            document = f"{date_str} {dept_name}의 {role_name}는 {doctor_name}입니다. 연락처는 {phone_number}입니다."
            
            # 진행 상황 로그 (100개마다 출력)
            if count % 100 == 0 and count > 0:
                print(f"  {count}개 처리 완료...")
            
            # 임베딩 생성
            embedding = model.encode(document)
            
            # 벡터와 메타데이터 추가
            vectors.append(embedding)
            metadata_list.append({
                "text": document,
                "date": date_str,
                "department": dept_name,
                "role": role_name,
                "name": doctor_name,
                "phone": phone_number,
                "schedule_id": int(schedule.id)
            })
        
        print(f"벡터 데이터 {len(vectors)}개를 생성했습니다.")
        
        # 벡터 스토어에 데이터 추가
        if vectors:
            vector_store.add_vectors(vectors, metadata_list)
            print(f"===== 벡터 DB 업데이트 완료: {len(vectors)}개 추가됨 =====")
            return {"status": "success", "message": f"{len(vectors)}개의 문서가 벡터 DB에 추가되었습니다."}
        else:
            print("추가할 데이터가 없습니다.")
            return {"status": "success", "message": "추가할 데이터가 없습니다."}
            
    except Exception as e:
        import traceback
        print(f"벡터 DB 업데이트 오류: {e}")
        traceback.print_exc()
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

def parse_date_reference(message: str):
    """사용자 메시지에서 날짜 참조 추출 (오늘, 내일 등)"""
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    
    # 날짜 묻는 질문 처리
    date_question = re.search(r"(오늘|지금).*(날짜|몇월\s*몇일)", message)
    if date_question:
        return today.strftime('%Y-%m-%d')
    
    # '어제', '오늘', '내일' 키워드 처리
    if "어제" in message:
        return yesterday.strftime('%Y-%m-%d')
    elif "내일" in message:
        return tomorrow.strftime('%Y-%m-%d')
    elif "오늘" in message:
        return today.strftime('%Y-%m-%d')
    
    # '5월 10일', '10일' 형식 처리
    date_pattern = re.search(r'(\d{1,2})월\s*(\d{1,2})일', message)
    if date_pattern:
        month = int(date_pattern.group(1))
        day = int(date_pattern.group(2))
        # 년도는 올해 또는 다음해로 설정 (현재 월보다 이전 월이면 다음해)
        year = today.year if month >= today.month else today.year + 1
        try:
            parsed_date = datetime(year, month, day)
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            # 유효하지 않은 날짜 처리
            return None
    
    # 단순히 '10일'처럼 일만 명시된 경우
    day_pattern = re.search(r'(\d{1,2})일', message)
    if day_pattern:
        day = int(day_pattern.group(1))
        # 같은 달로 가정
        month = today.month
        year = today.year
        
        # 현재 날짜보다 이전이면 다음 달로 설정
        if day < today.day:
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1
        
        try:
            parsed_date = datetime(year, month, day)
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

# Django ORM 호출을 위한 동기 함수
def get_all_departments():
    """부서 목록을 가져오는 동기 함수"""
    return [dept.name for dept in Department.objects.all()]

# 동기 함수를 비동기로 변환
get_all_departments_async = sync_to_async(get_all_departments)

async def extract_entities(message: str):
    """사용자 메시지에서 주요 엔티티 추출"""
    entities = {}
    
    # 날짜 추출
    date = parse_date_reference(message)
    if date:
        entities["date"] = date
    
    # 날짜 묻는 질문인지 확인
    if re.search(r"(오늘|지금).*(날짜|몇월\s*몇일)", message):
        entities["date_question"] = True
    
    # 부서 추출 (Django DB에서 부서명 가져오기)
    departments = await get_all_departments_async()
    
    # 부서명 매칭 - 가장 긴 부서명부터 매칭 시도 (예: "정형외과"가 "외과"보다 우선)
    matched_dept = None
    max_length = 0
    
    # 모든 부서명을 길이 기준 내림차순으로 정렬
    sorted_depts = sorted(departments, key=len, reverse=True)
    
    for dept in sorted_depts:
        if dept in message:
            # 더 긴 부서명이 매칭된 경우에만 업데이트
            if len(dept) > max_length:
                matched_dept = dept
                max_length = len(dept)
    
    if matched_dept:
        entities["department"] = matched_dept
        print(f"부서 매칭: '{matched_dept}'")
    
    # 구체적인 시간 추출 (HH시, H시, 오전/오후 H시 등)
    time_pattern = re.search(r'(\d{1,2})(?:시|:00|:30|시\s?(?:반|정각)?)', message)
    if time_pattern:
        hour = int(time_pattern.group(1))
        # 12시간제 처리 (오후 2시 → 14시)
        if '오후' in message and hour < 12:
            hour += 12
        elif '아침' in message and hour >= 12:
            hour = hour % 12
        
        # 시간을 24시간제로 저장
        entities["specific_hour"] = hour
        print(f"특정 시간 추출됨: {hour}시")
    
    # 시간대 추출 (아침, 오전, 오후, 저녁, 야간 등)
    time_keywords = {
        '아침': '08:00 - 12:00',
        '오전': '08:00 - 12:00',
        '점심': '12:00 - 14:00',
        '오후': '14:00 - 18:00',
        '저녁': '18:00 - 22:00',
        '밤': '22:00 - 08:00',
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
        '야간': '당직의',
        '야간 근무': '당직의', 
        '밤': '당직의',
        '밤 근무': '당직의',
        '수술': '수술의', 
        '수술의': '수술의',
        '수술 담당': '수술의',
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
    
    # 역할이 없지만 '누구'라는 표현이 있으면 일반적인 담당의 찾기
    if 'role' not in entities and ('누구' in message or '담당' in message):
        entities["role"] = '담당의'
    
    # 연락처 요청 여부
    if "번호" in message or "연락처" in message or "전화" in message or "폰" in message:
        entities["phone_requested"] = True
    
    return entities

@app.get("/", response_class=HTMLResponse)
async def get_root():
    """루트 경로에 접속하면 챗봇 인터페이스 HTML 반환"""
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
                <p>챗봇 인터페이스를 불러올 수 없습니다.</p>
                <p>API 엔드포인트: <code>/chat</code>에 POST 요청을 보내세요.</p>
            </body>
        </html>
        """

# Django ORM을 사용하는 동기 함수들을 정의
def get_schedule_from_db(date_str, dept_name, role_name=None, time_range=None, night_shift=False, specific_hour=None):
    """Django DB에서 스케줄 정보를 가져오는 동기 함수"""
    
    # 쿼리 기본 설정
    query = Schedule.objects.filter(
        date=date_str,
        doctor__department__name=dept_name
    ).select_related('doctor', 'work_schedule')
    
    print(f"조회 기준: 날짜={date_str}, 부서={dept_name}, 역할={role_name}, 시간대={time_range}, 특정시간={specific_hour}")
    
    # 스케줄 목록 가져오기
    all_schedules = list(query.all())
    if not all_schedules:
        print(f"해당 날짜/부서에 스케줄이 없습니다: {date_str}, {dept_name}")
        return None
    
    # 디버깅: 모든 스케줄 출력
    for i, schedule in enumerate(all_schedules):
        print(f"  스케줄 {i+1}: {schedule.work_schedule}, {schedule.doctor.name}")
    
    # 시간이 특정되지 않고 역할도 지정되지 않은 경우 모든 스케줄 반환
    if specific_hour is None and role_name is None and time_range is None:
        print("시간이나 역할이 특정되지 않아 모든 스케줄을 반환합니다.")
        return all_schedules
    
    # 특정 시간이 지정된 경우 (가장 우선)
    if specific_hour is not None:
        matching_schedules = []
        for schedule in all_schedules:
            try:
                # work_schedule 문자열에서 시간 추출 (예: "08:00 - 16:00")
                times = str(schedule.work_schedule).split(' - ')
                if len(times) == 2:
                    start_hour = int(times[0].split(':')[0])
                    end_hour = int(times[1].split(':')[0])
                    
                    # 경계 처리: 종료 시간이 시작 시간보다 작으면 다음 날
                    if end_hour < start_hour:
                        end_hour += 24
                    
                    print(f"    시간 비교: {start_hour} <= {specific_hour} < {end_hour}")
                    # 특정 시간이 시작 시간과 종료 시간 사이에 있는지 확인
                    if start_hour <= specific_hour < end_hour:
                        matching_schedules.append(schedule)
                        print(f"    ✓ 시간 일치: {schedule.work_schedule}")
            except Exception as e:
                print(f"    시간 파싱 오류: {e}")
                continue
        
        if matching_schedules:
            return matching_schedules[0]
    
    # 당직의 조회 로직
    if role_name and ('당직의' in role_name or '당직' in role_name):
        # 현재 시간 기준 처리 (특정 시간이 없는 경우)
        current_hour = datetime.now().time().hour if specific_hour is None else specific_hour
        
        # 밤 시간대 (20시 이후 or 8시 이전)
        if night_shift or current_hour >= 20 or current_hour < 8:
            # 야간/저녁 시간대 스케줄 우선 조회
            for schedule in all_schedules:
                schedule_str = str(schedule.work_schedule)
                if any(time in schedule_str for time in ['20:00', '21:00', '22:00', '23:00', '00:00']):
                    return schedule
        
        # 특정 시간에 해당하는 스케줄 찾기
        else:
            for schedule in all_schedules:
                times = str(schedule.work_schedule).split(' - ')
                if len(times) == 2:
                    try:
                        start_hour = int(times[0].split(':')[0])
                        end_hour = int(times[1].split(':')[0])
                        
                        # 경계 처리
                        if end_hour < start_hour:
                            end_hour += 24
                            
                        if start_hour <= current_hour < end_hour:
                            return schedule
                    except:
                        continue
    
    # 특정 시간대가 지정된 경우
    if time_range:
        # 시간 범위에서 시작 시간 추출
        time_match = re.search(r'(\d{1,2}):(\d{2})', time_range)
        if time_match:
            start_hour = time_match.group(1).zfill(2)
            for schedule in all_schedules:
                if str(schedule.work_schedule).startswith(f"{start_hour}:"):
                    return schedule
    
    # 역할명으로 필터링 (예: 수술의)
    if role_name:
        for schedule in all_schedules:
            if role_name.lower() in str(schedule.work_schedule).lower():
                return schedule
    
    # 기본적으로 현재 시간에 해당하는 스케줄 찾기
    current_hour = datetime.now().time().hour if specific_hour is None else specific_hour
    current_hour_str = f"{current_hour:02d}:00"
    
    for schedule in all_schedules:
        times = str(schedule.work_schedule).split(' - ')
        if len(times) == 2:
            try:
                start_time = times[0].strip()
                end_time = times[1].strip()
                
                # 시간 비교
                start_hour = int(start_time.split(':')[0])
                end_hour = int(end_time.split(':')[0])
                
                # 경계 처리
                if end_hour < start_hour:
                    end_hour += 24
                
                if start_hour <= current_hour < end_hour:
                    return schedule
            except:
                continue
    
    # 모든 조건에 맞지 않으면, 첫 번째 스케줄 반환
    return all_schedules[0]

# 동기 함수를 비동기로 변환
get_schedule_from_db_async = sync_to_async(get_schedule_from_db)

@app.get("/update-vectors")
async def update_vectors():
    """벡터 DB를 Django DB의 최신 데이터로 업데이트"""
    if vector_store is None:
        return {"status": "error", "message": "벡터 DB가 초기화되지 않았습니다. 기능을 사용할 수 없습니다."}
    
    result = await update_vector_db_from_django_async()
    return result

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        message = req.message
        print(f"\n===== 새 채팅 요청: '{message}' =====")
        
        # 1. 엔티티 추출
        try:
            entities = await extract_entities(message)
            print(f"추출된 엔티티: {entities}")
        except Exception as e:
            print(f"엔티티 추출 오류: {e}")
            return {"answer": f"엔티티 추출 중 오류가 발생했습니다: {str(e)}"}
        
        # 날짜 질문 처리
        if "date_question" in entities:
            today = datetime.now()
            weekday_map = {0: '월요일', 1: '화요일', 2: '수요일', 3: '목요일', 4: '금요일', 5: '토요일', 6: '일요일'}
            weekday = weekday_map[today.weekday()]
            return {"answer": f"오늘은 {today.strftime('%Y년 %m월 %d일')} {weekday}입니다."}
        
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
                        
                        if "phone_requested" in entities:
                            schedule_info = [f"{str(s.work_schedule)}: {s.doctor.name} (연락처: {s.doctor.phone_number})" 
                                            for s in sorted_schedules]
                        else:
                            schedule_info = [f"{str(s.work_schedule)}: {s.doctor.name}" 
                                            for s in sorted_schedules]
                        
                        response = f"{date_str} {dept_name} 당직표:\n" + "\n".join(schedule_info)
                        print(f"응답: {response}")
                        return {"answer": response}
                    # 단일 스케줄 반환인 경우
                    else:
                        if isinstance(schedule_result, list):
                            schedule = schedule_result[0]
                        else:
                            schedule = schedule_result
                            
                        print(f"DB 직접 조회 성공: {schedule.date} - {schedule.doctor.name}, 시간={schedule.work_schedule}")
                        if "phone_requested" in entities:
                            response = f"{date_str} {dept_name} {str(schedule.work_schedule)}의 연락처는 {schedule.doctor.name} {schedule.doctor.phone_number}입니다."
                        else:
                            response = f"{date_str} {dept_name} {str(schedule.work_schedule)}는 {schedule.doctor.name}입니다."
                        
                        print(f"응답: {response}")
                        return {"answer": response}
                else:
                    print(f"DB 직접 조회 실패: {date_str}, {dept_name}에 해당하는 스케줄이 없습니다.")
                    # 벡터 검색으로 폴백
            except Exception as e:
                print(f"DB 직접 조회 오류: {e}")
                import traceback
                traceback.print_exc()
                # 벡터 검색으로 폴백
        
        # 4. 벡터 검색 시도 (FAISS 벡터 스토어가 사용 가능한 경우)
        if vector_store is not None:
            try:
                print("벡터 검색 시작...")
                # 메시지 임베딩
                query_embedding = model.encode(message).tolist()
                
                # 벡터 검색 수행
                search_results = vector_store.search(query_embedding, k=20)  # 더 많은 결과 가져오기
                
                if search_results and len(search_results) > 0:
                    print(f"벡터 검색 결과: {len(search_results)}개 발견")
                    
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
                            
                            # 시간 순으로 정렬 (시작 시간 기준)
                            matching_schedules.sort(key=lambda m: int(m['role'].split(' - ')[0].split(':')[0]))
                            
                            if "phone_requested" in entities:
                                schedule_info = [f"{m['role']}: {m['name']} (연락처: {m['phone']})" for m in matching_schedules]
                            else:
                                schedule_info = [f"{m['role']}: {m['name']}" for m in matching_schedules]
                            
                            response = f"{entities['date']} {entities['department']} 당직표:\n" + "\n".join(schedule_info)
                            print(f"응답: {response}")
                            return {"answer": response}
                    
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
                                        
                                        # 경계 처리
                                        if end_hour < start_hour:
                                            end_hour += 24
                                        
                                        current_time_match = start_hour <= specific_hour < end_hour
                                except:
                                    current_time_match = True  # 파싱 실패 시 기본값
                            
                            if current_time_match or specific_hour is None:
                                if "phone_requested" in entities:
                                    response = f"{date_str} {dept_name} {str(schedule.work_schedule)}의 연락처는 {schedule.doctor.name} {schedule.doctor.phone_number}입니다."
                                else:
                                    response = f"{date_str} {dept_name} {str(schedule.work_schedule)}는 {schedule.doctor.name}입니다."
                                
                                print(f"응답: {response}")
                                return {"answer": response}
                            else:
                                # 현재 시간에 해당하는 당직의가 없음
                                response = f"현재 시간({specific_hour}시)에는 {dept_name}의 당직 의사가 없습니다."
                                print(f"응답: {response}")
                                return {"answer": response}
                        else:
                            print(f"DB 조회 실패: {date_str}에 해당하는 스케줄이 없습니다.")
                            response = f"{dept_name}의 당직 정보를 찾을 수 없습니다."
                            print(f"응답: {response}")
                            return {"answer": response}
                    
                    # 벡터 검색 결과 중 최선의 결과 선택
                    if not best_match and search_results:
                        # 유사도 기반 선택 (점수가 가장 높은 것)
                        best_match = search_results[0]["entity"]
                        print(f"유사도 기반 최적 결과 선택: {best_match}")
                    
                    if best_match:
                        # 결과가 실제 질문과 관련이 있는지 확인
                        if 'department' in entities and best_match.get('department') != entities['department']:
                            response = f"{entities['department']}의 당직 정보를 찾을 수 없습니다."
                        else:
                            if "phone_requested" in entities:
                                response = f"{best_match['date']} {best_match['department']} {best_match['role']}의 연락처는 {best_match['name']} {best_match['phone']}입니다."
                            else:
                                response = f"{best_match['date']} {best_match['department']} {best_match['role']}는 {best_match['name']}입니다."
                    else:
                        response = "죄송합니다. 질문에 맞는 당직 정보를 찾을 수 없습니다."
                else:
                    print("벡터 검색 결과가 없습니다.")
                    response = "죄송합니다. 질문에 맞는 정보를 찾을 수 없습니다. 다른 방식으로 질문해 주세요."
            except Exception as e:
                print(f"벡터 검색 오류: {e}")
                import traceback
                traceback.print_exc()
                response = f"검색 중 오류가 발생했습니다: {str(e)}"
        else:
            response = "벡터 검색 엔진이 준비되지 않았습니다."
        
        print(f"응답: {response}")
        return {"answer": response}
    except Exception as e:
        # 전체 예외 처리
        print(f"Chat 엔드포인트 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"answer": f"요청 처리 중 오류가 발생했습니다: {str(e)}"} 