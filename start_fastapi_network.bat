@echo off
cls
echo ========================================
echo     FastAPI 서버 (네트워크 접근 가능)
echo ========================================
echo.

echo [정보] 네트워크에서 접근 가능한 FastAPI 서버를 시작합니다.
echo [정보] 서버 주소: http://10.20.30.215:8080
echo [정보] 로컬 주소: http://localhost:8080
echo.

cd /d "C:\Users\emr4\Desktop\oncall_project\chatbot_webapp\backend"

echo [1/3] 현재 디렉토리: %CD%
echo.

echo [2/3] Python 패키지 확인...
python -c "import fastapi, uvicorn; print('✅ 필요한 패키지가 모두 설치되어 있습니다.')"
if errorlevel 1 (
    echo ❌ FastAPI 또는 Uvicorn이 설치되지 않았습니다!
    echo 해결: pip install fastapi uvicorn
    pause
    exit /b 1
)
echo.

echo [3/3] FastAPI 서버 시작 (네트워크 접근 허용)...
echo.
echo 🌐 네트워크 접근 URL:
echo    - http://10.20.30.215:8080/departments
echo    - http://10.20.30.215:8080/docs
echo.
echo 🏠 로컬 접근 URL:
echo    - http://localhost:8080/departments  
echo    - http://localhost:8080/docs
echo.
echo ⚠️ 서버 종료: Ctrl+C
echo.

REM 0.0.0.0으로 바인딩하여 모든 네트워크 인터페이스에서 접근 가능
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

pause 