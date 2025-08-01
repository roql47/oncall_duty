#!/usr/bin/env python3
"""
챗봇 로깅 테스트 스크립트
React 프론트엔드에서 FastAPI로 요청을 보낼 때 로깅이 제대로 되는지 테스트
"""

import requests
import json
import time
from datetime import datetime

# 테스트 설정
FASTAPI_URL = "http://localhost:8080/chat"
TEST_MESSAGES = [
    "오늘 순환기내과 당직 누구야?",
    "내일 외과 당직 연락처 알려줘",
    "정형외과 당직의 번호는?",
    "응급의학과 당직 일정 알려줘"
]

def test_chatbot_logging():
    """챗봇 API 테스트 및 로깅 확인"""
    print("🚀 챗봇 로깅 테스트 시작")
    print("=" * 50)
    
    # 세션 ID 생성 (React 앱과 동일한 방식)
    session_id = f"test_{int(time.time())}_{hash(str(datetime.now())) % 10000}"
    
    # 클라이언트 정보 (React 앱과 유사하게 구성)
    client_info = {
        "userAgent": "Mozilla/5.0 (Test) AppleWebKit/537.36",
        "platform": "Test Platform",
        "language": "ko-KR",
        "screenSize": "1920x1080",
        "timestamp": datetime.now().isoformat(),
        "referrer": "http://localhost:3000",
        "url": "http://localhost:3000/test",
    }
    
    for i, message in enumerate(TEST_MESSAGES, 1):
        print(f"\n📝 테스트 {i}/{len(TEST_MESSAGES)}: {message}")
        
        # 요청 데이터 구성
        request_data = {
            "message": message,
            "session_id": session_id,
            "client_info": client_info,
            "source": "test_script",
            "version": "1.0.0"
        }
        
        # 요청 헤더
        headers = {
            "Content-Type": "application/json",
            "X-Session-ID": session_id,
            "X-Client-Info": json.dumps(client_info)
        }
        
        try:
            # API 요청 보내기
            start_time = time.time()
            response = requests.post(
                FASTAPI_URL, 
                json=request_data, 
                headers=headers,
                timeout=30
            )
            response_time = (time.time() - start_time) * 1000
            
            print(f"  ✅ 응답 시간: {response_time:.2f}ms")
            print(f"  📊 상태 코드: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                print(f"  💬 응답: {answer[:100]}{'...' if len(answer) > 100 else ''}")
            else:
                print(f"  ❌ 오류 응답: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 요청 실패: {e}")
        
        # 요청 간 잠시 대기
        time.sleep(1)
    
    print("\n" + "=" * 50)
    print("✅ 테스트 완료!")
    print("\n📁 로그 파일 확인:")
    print("  - logs/fastapi/chatbot/fastapi_chatbot_*.log")
    print("  - logs/fastapi/chatbot/conversations_*.json")
    print("  - logs/fastapi/chatbot/fallback_*.txt (오류 시)")

def check_log_files():
    """로그 파일 존재 여부 확인"""
    import os
    from pathlib import Path
    
    print("\n🔍 로그 파일 상태 확인:")
    
    log_dir = Path("logs/fastapi/chatbot")
    if not log_dir.exists():
        print("  ❌ 로그 디렉토리가 존재하지 않습니다.")
        return
    
    log_files = list(log_dir.glob("*.log")) + list(log_dir.glob("*.json")) + list(log_dir.glob("*.txt"))
    
    if not log_files:
        print("  ⚠️  로그 파일이 없습니다.")
        return
    
    for log_file in sorted(log_files):
        size = log_file.stat().st_size
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        print(f"  📄 {log_file.name}: {size}B, 수정: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    print("🧪 챗봇 로깅 테스트 도구")
    print("이 스크립트는 React 프론트엔드에서 FastAPI로 보내는 요청을 시뮬레이션합니다.")
    print()
    
    # 사전 로그 파일 상태 확인
    check_log_files()
    
    # 챗봇 테스트 실행
    test_chatbot_logging()
    
    # 사후 로그 파일 상태 확인
    check_log_files() 