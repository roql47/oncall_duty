@echo off
echo ============================================
echo      FastAPI 챗봇 서버 시작
echo ============================================
echo.

echo 📂 디렉토리 이동 중...
cd /d "C:\Users\emr4\Desktop\oncall_project\chatbot_webapp\backend"

echo 📋 필수 패키지 확인 중...
python -c "import fastapi, uvicorn, faiss, sentence_transformers; print('✅ 필수 패키지가 모두 설치되어 있습니다.')" 2>nul
if errorlevel 1 (
    echo ❌ 필수 패키지가 설치되지 않았습니다.
    echo 💡 다음 명령어를 실행하여 패키지를 설치하세요:
    echo    pip install fastapi uvicorn sentence-transformers faiss-cpu
    echo.
    pause
    exit /b 1
)

echo 🚀 FastAPI 서버 시작 중... (포트 8080)
echo.
echo 💡 서버 접속 주소: http://localhost:8080
echo 💡 React 챗봇에서 사용: http://localhost:3000
echo 💡 서버를 종료하려면 Ctrl+C를 누르세요
echo.
echo ⏳ 서버가 시작되면 아래와 같은 메시지가 표시됩니다:
echo    "Application startup complete."
echo.

uvicorn main:app --host 127.0.0.1 --port 8080 --reload

if errorlevel 1 (
    echo.
    echo ❌ FastAPI 서버 시작에 실패했습니다.
    echo 💡 해결 방법:
    echo    1. Python이 설치되어 있는지 확인
    echo    2. 필수 패키지가 설치되어 있는지 확인
    echo    3. 포트 8080이 다른 프로그램에 의해 사용 중인지 확인
    echo.
)

pause 