from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from datetime import datetime, timedelta
import re

app = FastAPI()

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터 로드
with open("duty_data.json", encoding="utf-8") as f:
    DUTY_DATA = json.load(f)

class ChatRequest(BaseModel):
    message: str

# 간단한 자연어 파싱 함수

def parse_query(message: str):
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    date = today.strftime('%Y-%m-%d')
    dept = None
    role = None
    time = None
    phone = False

    # 날짜 파싱
    if "내일" in message:
        date = tomorrow.strftime('%Y-%m-%d')
    elif "오늘" in message:
        date = today.strftime('%Y-%m-%d')
    # 시간 파싱 (예: 내일 10시에)
    m = re.search(r"(오늘|내일)? ?(\d{1,2})시", message)
    if m:
        hour = int(m.group(2))
        base = today if (m.group(1) == "오늘" or not m.group(1)) else tomorrow
        dt = base.replace(hour=hour, minute=0, second=0, microsecond=0)
        date = dt.strftime('%Y-%m-%d')
        time = hour
    # 과 파싱
    for d in ["순환기내과", "외과", "내과", "정형외과", "응급의학과"]:
        if d in message:
            dept = d
            break
    # 역할 파싱
    for r in ["당직의", "수술의"]:
        if r in message:
            role = r
            break
    # 번호 요청 여부
    if "번호" in message or "연락처" in message:
        phone = True
    return date, dept, role, phone

@app.post("/chat")
async def chat(req: ChatRequest):
    message = req.message
    date, dept, role, phone = parse_query(message)
    res = "질문을 이해하지 못했습니다."
    if date and dept and role:
        try:
            info = DUTY_DATA[date][dept][role]
            if phone:
                res = f"{date} {dept} {role}의 연락처는 {info['이름']} {info['번호']}입니다."
            else:
                res = f"{date} {dept} {role}는 {info['이름']}입니다."
        except Exception:
            res = f"{date} {dept} {role} 정보를 찾을 수 없습니다."
    else:
        res = "날짜, 과, 역할을 명확히 입력해주세요."
    return {"answer": res} 