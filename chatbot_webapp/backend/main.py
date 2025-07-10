from fastapi import FastAPI, Request, Depends # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from pydantic import BaseModel # type: ignore
import json
import os
import sqlite3
import time
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

# Google의 Gemini API 통합
import google.generativeai as genai # type: ignore

# API 키 설정
GEMINI_API_KEY = "AIzaSyC-J3EZmtWoNiPJ7yzCwwAvY6ta5uny_9M"
genai.configure(api_key=GEMINI_API_KEY)

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

# SentenceTransformer 모델 로드 - 성능 최적화를 위해 더 빠른 모델 사용
print("임베딩 모델 로딩 중...")
# 더 빠른 성능을 위해 더 가벼운 모델 사용
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')  # 기존 모델보다 빠름

# GPU 사용 가능 여부 확인
import torch
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"사용할 디바이스: {device}")

# 모델을 GPU로 이동 (가능한 경우)
if torch.cuda.is_available():
    model = model.to(device)
    print("GPU 가속 활성화됨")
else:
    print("CPU 모드로 실행")

print("임베딩 모델 로딩 완료!")

# 성능 최적화를 위한 배치 크기 설정
# GPU 사용 시 더 큰 배치 크기로 설정
EMBEDDING_BATCH_SIZE = 300 if torch.cuda.is_available() else 200

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
    
    def add_vectors(self, vectors, metadata_list, incremental=False):
        """벡터와 메타데이터 추가"""
        if len(vectors) == 0:
            return
        
        # 벡터를 numpy 배열로 변환
        vectors_np = np.array(vectors).astype('float32')
        
        if incremental and self.index.ntotal > 0:
            # 증분 업데이트: 기존 벡터 유지하면서 새로운 벡터 추가
            self.index.add(vectors_np)
            self.metadata.extend(metadata_list)
            print(f"{len(vectors)}개의 벡터를 기존 {self.index.ntotal - len(vectors)}개에 추가했습니다.")
        else:
            # 전체 교체: 기존 인덱스 삭제하고 새로 생성
            self.index = faiss.IndexFlatIP(self.vector_dim)
            self.metadata = metadata_list
            self.index.add(vectors_np)
            print(f"{len(vectors)}개의 벡터를 새로 생성했습니다.")
        
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
try:
    vector_store = FAISSVectorStore(VECTOR_DIM)
    print("임베디드 벡터 검색 엔진이 준비되었습니다.")
except Exception as e:
    print(f"벡터 검색 초기화 오류: {e}")
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
        
        # 성능 최적화: 증분 업데이트 - 이미 처리된 스케줄 ID 확인
        existing_schedule_ids = set()
        if vector_store.metadata:
            existing_schedule_ids = {item.get('schedule_id') for item in vector_store.metadata if item.get('schedule_id')}
        
        # 새로운 스케줄만 필터링
        new_schedules = [s for s in schedules if s.id not in existing_schedule_ids]
        
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
            
            # 문서 텍스트 생성
            document = f"{date_str} {dept_name}의 {role_name}는 {doctor_name}입니다. 연락처는 {phone_number}입니다."
            documents.append(document)
            
            # 메타데이터 준비
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
            
            # GPU 사용 가능 시 더 빠른 처리
            batch_embeddings = model.encode(batch_docs, convert_to_numpy=True, show_progress_bar=False)
            all_embeddings.extend(batch_embeddings)
            
            # 진행 상황 업데이트 (배치 단위로)
            progress = 40 + int((i + len(batch_docs)) / len(documents) * 40)  # 40%~80% 범위
            update_progress["progress"] = progress
            update_progress["message"] = f"임베딩 생성 중... ({i + len(batch_docs)}/{len(documents)})"
            
            batch_num = i//EMBEDDING_BATCH_SIZE + 1
            if i == 0:
                print(f"배치 {batch_num} 완료: {len(batch_docs)}개 문서 처리")
            else:
                current_time = time.time() - start_time
                print(f"배치 {batch_num} 완료: {len(batch_docs)}개 문서 처리 ({current_time:.2f}초 경과)")
        
        embedding_time = time.time() - start_time
        print(f"임베딩 생성 완료! 소요시간: {embedding_time:.2f}초")
        print(f"벡터 데이터 {len(all_embeddings)}개를 생성했습니다.")
        
        # 벡터 스토어에 데이터 추가 (증분 업데이트 사용)
        update_progress["message"] = "벡터 DB에 데이터 저장 중..."
        update_progress["progress"] = 85
        
        if all_embeddings:
            # 증분 업데이트로 새로운 벡터만 추가
            vector_store.add_vectors(all_embeddings, metadata_list, incremental=True)
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

# Gemini 모델을 사용한 RAG 요청을 위한 클래스
class RAGRequest(BaseModel):
    query: str
    max_results: int = 10

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
        print(f"'내일' 키워드 감지됨 - 날짜 변환: {tomorrow.strftime('%Y-%m-%d')}")
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
    
    # 단순히 '9일'처럼 일만 명시된 경우
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
        
        # 내일 키워드 있지만 날짜 필터링 결과가 없는 경우
        if "내일" in query and not date_reference:
            tomorrow_results = [r for r in all_results if r["entity"]["date"] == tomorrow_date]
            
            if tomorrow_results:
                print(f"'내일' 키워드를 위한 특별 처리: 내일({tomorrow_date})에 해당하는 결과 {len(tomorrow_results)}개 찾음")
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
    
    # 쿼리 기본 설정
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
        all_schedules = list(query.all())
    
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
                        # 시작 시간을 분 단위로 변환
                        start_parts = times[0].split(':')
                        start_hour = int(start_parts[0])
                        start_minute = int(start_parts[1]) if len(start_parts) > 1 else 0
                        start_total_minutes = start_hour * 60 + start_minute
                        
                        # 종료 시간을 분 단위로 변환
                        end_parts = times[1].split(':')
                        end_hour = int(end_parts[0])
                        end_minute = int(end_parts[1]) if len(end_parts) > 1 else 0
                        end_total_minutes = end_hour * 60 + end_minute
                        
                        # 현재 시간을 분 단위로 변환
                        current_total_minutes = current_hour * 60
                        
                        # 시작 시간이 종료 시간과 같거나 더 클 경우 익일로 처리
                        if end_total_minutes <= start_total_minutes:
                            end_total_minutes += 24 * 60
                        
                        # current_hour 정규화 (익일 새벽 시간 처리)
                        current_total_minutes_normalized = current_total_minutes
                        if current_hour < 12 and start_hour > 12:
                            current_total_minutes_normalized = current_total_minutes + 24 * 60
                            
                        if start_total_minutes <= current_total_minutes_normalized < end_total_minutes:
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
                
                # 시간을 분 단위로 변환
                # 시작 시간을 분 단위로 변환
                start_parts = start_time.split(':')
                start_hour = int(start_parts[0])
                start_minute = int(start_parts[1]) if len(start_parts) > 1 else 0
                start_total_minutes = start_hour * 60 + start_minute
                
                # 종료 시간을 분 단위로 변환
                end_parts = end_time.split(':')
                end_hour = int(end_parts[0])
                end_minute = int(end_parts[1]) if len(end_parts) > 1 else 0
                end_total_minutes = end_hour * 60 + end_minute
                
                # 현재 시간을 분 단위로 변환
                current_total_minutes = current_hour * 60
                
                # 시작 시간이 종료 시간과 같거나 더 클 경우 익일로 처리
                if end_total_minutes <= start_total_minutes:
                    end_total_minutes += 24 * 60
                
                # current_hour 정규화 (익일 새벽 시간 처리)
                current_total_minutes_normalized = current_total_minutes
                if current_hour < 12 and start_hour > 12:
                    current_total_minutes_normalized = current_total_minutes + 24 * 60
                    
                if start_total_minutes <= current_total_minutes_normalized < end_total_minutes:
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

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        message = req.message
        print(f"\n===== 새 채팅 요청: '{message}' =====")
        
        # 1. 엔티티 추출
        try:
            entities = await extract_entities(message)
            print(f"추출된 엔티티: {entities}")
            
            # 이미 extract_entities에서 날짜 조정을 완료했으므로 여기서는 제거
            
        except Exception as e:
            print(f"엔티티 추출 오류: {e}")
            
            # 엔티티 추출이 실패하면 RAG 기반 응답으로 대체
            try:
                print("엔티티 추출 실패, RAG로 대체합니다...")
                rag_request = RAGRequest(query=message, max_results=10)
                rag_response = await rag_query(rag_request)
                
                if rag_response.get("status") == "success" and "answer" in rag_response:
                    return {"answer": rag_response["answer"]}
                else:
                    return {"answer": rag_response.get("message", "죄송합니다. 답변을 생성할 수 없습니다.")}
            except Exception as rag_error:
                print(f"RAG 대체 시도 오류: {rag_error}")
                return {"answer": f"엔티티 추출 및 RAG 응답 생성 중 오류가 발생했습니다: {str(e)}"}
        
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
                        
                        schedule_info = [f"• {str(s.work_schedule)}: {s.doctor.name} (연락처: {s.doctor.phone_number})" 
                                       for s in sorted_schedules]
                        
                        response = f"[{date_str}] {dept_name} 당직표:\n\n" + "\n".join(schedule_info)
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
                            response = f"[{date_str}] {dept_name} {str(schedule.work_schedule)}의 연락처는 {schedule.doctor.name} {schedule.doctor.phone_number}입니다."
                        else:
                            response = f"[{date_str}] {dept_name} {str(schedule.work_schedule)}는 {schedule.doctor.name}입니다."
                        
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
                            
                            # best_match가 있으면 바로 응답 반환
                            if best_match:
                                if "phone_requested" in entities:
                                    response = f"[{best_match['date']}] {best_match['department']} {best_match['role']}의 연락처는 {best_match['name']} {best_match['phone']}입니다."
                                else:
                                    response = f"[{best_match['date']}] {best_match['department']} {best_match['role']}는 {best_match['name']}입니다."
                                
                                print(f"응답: {response}")
                                return {"answer": response}
                            
                            # 전체 당직표 모드
                            # 시간 순으로 정렬 (시작 시간 기준)
                            matching_schedules.sort(key=lambda m: int(m['role'].split(' - ')[0].split(':')[0]))
                            
                            if "phone_requested" in entities:
                                schedule_info = [f"• {m['role']}: {m['name']} (연락처: {m['phone']})" for m in matching_schedules]
                            else:
                                schedule_info = [f"• {m['role']}: {m['name']}" for m in matching_schedules]
                            
                            response = f"[{entities['date']}] {entities['department']} 당직표:\n\n" + "\n".join(schedule_info)
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
                                if "phone_requested" in entities:
                                    response = f"[{date_str}] {dept_name} {str(schedule.work_schedule)}의 연락처는 {schedule.doctor.name} {schedule.doctor.phone_number}입니다."
                                else:
                                    response = f"[{date_str}] {dept_name} {str(schedule.work_schedule)}는 {schedule.doctor.name}입니다."
                                
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
                                response = f"[{best_match['date']}] {best_match['department']} {best_match['role']}의 연락처는 {best_match['name']} {best_match['phone']}입니다."
                            else:
                                response = f"[{best_match['date']}] {best_match['department']} {best_match['role']}는 {best_match['name']}입니다."
                    else:
                        response = "죄송합니다. 질문에 맞는 당직 정보를 찾을 수 없습니다."
                else:
                    print("벡터 검색 결과가 없습니다.")
                    
                    # Gemini RAG로 대체 시도
                    try:
                        print("벡터 검색 결과가 없어, Gemini RAG로 대체 시도합니다...")
                        rag_request = RAGRequest(query=message, max_results=10)
                        rag_response = await rag_query(rag_request)
                        
                        if rag_response.get("status") == "success" and "answer" in rag_response:
                            return {"answer": rag_response["answer"]}
                        else:
                            response = "죄송합니다. 질문에 맞는 정보를 찾을 수 없습니다. 다른 방식으로 질문해 주세요."
                    except Exception as rag_error:
                        print(f"Gemini RAG 대체 시도 오류: {rag_error}")
                        response = "죄송합니다. 질문에 맞는 정보를 찾을 수 없습니다. 다른 방식으로 질문해 주세요."
            except Exception as e:
                print(f"벡터 검색 오류: {e}")
                import traceback
                traceback.print_exc()
                
                # Gemini RAG로 대체 시도
                try:
                    print("벡터 검색 오류로 Gemini RAG로 대체 시도합니다...")
                    rag_request = RAGRequest(query=message, max_results=10)
                    rag_response = await rag_query(rag_request)
                    
                    if rag_response.get("status") == "success" and "answer" in rag_response:
                        return {"answer": rag_response["answer"]}
                    else:
                        response = f"검색 중 오류가 발생했습니다: {str(e)}"
                except Exception as rag_error:
                    print(f"Gemini RAG 대체 시도 오류: {rag_error}")
                    response = f"검색 중 오류가 발생했습니다: {str(e)}"
        else:
            # 벡터 스토어가 없는 경우 Gemini RAG로 대체 시도
            try:
                print("벡터 스토어가 없어 Gemini RAG로 대체 시도합니다...")
                rag_request = RAGRequest(query=message, max_results=10)
                rag_response = await rag_query(rag_request)
                
                if rag_response.get("status") == "success" and "answer" in rag_response:
                    return {"answer": rag_response["answer"]}
                else:
                    response = "벡터 검색 엔진이 준비되지 않았습니다."
            except Exception as rag_error:
                print(f"Gemini RAG 대체 시도 오류: {rag_error}")
                response = "벡터 검색 엔진이 준비되지 않았습니다."
        
        print(f"응답: {response}")
        return {"answer": response}
    except Exception as e:
        # 전체 예외 처리
        print(f"Chat 엔드포인트 오류: {e}")
        import traceback
        traceback.print_exc()
        
        # 최후의 수단으로 Gemini RAG 시도
        try:
            print("전체 예외 발생, 마지막으로 Gemini RAG 시도...")
            rag_request = RAGRequest(query=req.message, max_results=10)
            rag_response = await rag_query(rag_request)
            
            if rag_response.get("status") == "success" and "answer" in rag_response:
                return {"answer": rag_response["answer"]}
        except Exception:
            pass
            
        return {"answer": f"요청 처리 중 오류가 발생했습니다: {str(e)}"}

# Django ORM 호출을 위한 동기 함수
def get_all_departments():
    """부서 목록을 가져오는 동기 함수"""
    return [dept.name for dept in Department.objects.all()]

# 동기 함수를 비동기로 변환
get_all_departments_async = sync_to_async(get_all_departments)

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
    if "지금" in message:
        today = datetime.now()
        entities["date"] = today.strftime('%Y-%m-%d')
        print(f"'지금' 키워드 감지 - 현재 날짜 추가: {entities['date']}")
    
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
    
    # 부서 추출 (Django DB에서 부서명 가져오기)
    departments = await get_all_departments_async()
    
    # 부서명 매칭 - 가장 긴 부서명부터 매칭 시도 (예: "정형외과"가 "외과"보다 우선)
    matched_dept = None
    max_length = 0
    
    # 모든 부서명을 길이 기준 내림차순으로 정렬
    sorted_depts = sorted(departments, key=len, reverse=True)
    
    # 메시지에서 띄어쓰기 제거한 버전도 준비
    message_no_space = message.replace(" ", "")
    
    for dept in sorted_depts:
        # 띄어쓰기가 있는 원본 부서명으로 매칭 시도
        if dept in message:
            if len(dept) > max_length:
                matched_dept = dept
                max_length = len(dept)
        # 띄어쓰기를 제거한 부서명으로도 매칭 시도
        elif dept.replace(" ", "") in message_no_space:
            if len(dept) > max_length:
                matched_dept = dept
                max_length = len(dept)
    
    if matched_dept:
        entities["department"] = matched_dept
        print(f"부서 매칭: '{matched_dept}'")
    
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