@echo off
echo ============================================
echo      FastAPI 챗봇 서버 시작 (안전 모드)
echo ============================================
echo.

echo 📂 작업 디렉토리 설정...
cd /d "C:\Users\emr4\Desktop\oncall_project\chatbot_webapp\backend"

echo 🔧 환경 변수 설정...
set PYTHONPATH=C:\Users\emr4\Desktop\oncall_project
set DJANGO_SETTINGS_MODULE=oncall_system.settings

echo 📋 Python 및 패키지 상태 확인...
python --version
if errorlevel 1 (
    echo ❌ Python이 설치되지 않았거나 PATH에 등록되지 않았습니다.
    pause
    exit /b 1
)

echo.
echo 📦 필수 패키지 확인 중...
python -c "
try:
    import fastapi, uvicorn, django
    print('✅ 기본 패키지 확인 완료')
    
    import faiss
    print('✅ FAISS 확인 완료')
    
    import sentence_transformers
    print('✅ SentenceTransformers 확인 완료')
    
    print('🎉 모든 필수 패키지가 준비되었습니다!')
except ImportError as e:
    print(f'❌ 패키지 누락: {e}')
    print('💡 다음 명령어로 설치하세요:')
    print('   pip install fastapi uvicorn django sentence-transformers faiss-cpu')
    exit(1)
"

if errorlevel 1 (
    echo.
    echo ❌ 필수 패키지가 설치되지 않았습니다.
    pause
    exit /b 1
)

echo.
echo 🚀 FastAPI 서버 시작 중... (포트 8080)
echo.
echo 📍 접속 주소:
echo    - FastAPI 서버:    http://localhost:8080
echo    - React 챗봇:      http://localhost:3000
echo    - API 문서:        http://localhost:8080/docs
echo.
echo 💡 팁:
echo    - 서버 종료: Ctrl+C 
echo    - 로그 확인: logs/fastapi/ 디렉토리
echo    - 연결 테스트: http://localhost:8080/departments
echo.
echo ⏳ 서버 시작 중... 잠시만 기다려주세요.
echo.

rem 서버 시작
uvicorn main:app --host 127.0.0.1 --port 8080 --reload --log-level info

rem 오류 처리
if errorlevel 1 (
    echo.
    echo ==========================================
    echo ❌ FastAPI 서버 시작 실패
    echo ==========================================
    echo.
    echo 🔍 가능한 원인:
    echo    1. 포트 8080이 이미 사용 중
    echo    2. 파이썬 패키지 설치 문제
    echo    3. Django 설정 오류
    echo    4. 로깅 시스템 문제
    echo.
    echo 🛠️ 해결 방법:
    echo    1. 다른 터미널에서 실행 중인 서버 종료
    echo    2. 포트 변경: --port 8081
    echo    3. 패키지 재설치: pip install -r requirements.txt
    echo    4. 로그 디렉토리 확인: logs/fastapi/
    echo.
    echo 📞 도움이 필요하면 오류 메시지를 확인하세요.
    echo.
) else (
    echo.
    echo ✅ FastAPI 서버가 정상적으로 종료되었습니다.
)

pause 