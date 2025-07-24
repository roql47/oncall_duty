@echo off
cls
echo =========================================
echo     FastAPI 서버 디버그 모드 시작
echo =========================================
echo.

echo [1/5] 작업 디렉토리 이동...
cd /d "C:\Users\emr4\Desktop\oncall_project\chatbot_webapp\backend"
echo 현재 위치: %CD%
echo.

echo [2/5] 파일 존재 확인...
if exist "main.py" (
    echo ✅ main.py 파일 확인됨
) else (
    echo ❌ main.py 파일이 없습니다!
    pause
    exit /b 1
)
echo.

echo [3/5] Python 실행 테스트...
python --version
if errorlevel 1 (
    echo ❌ Python이 설치되지 않았습니다!
    pause
    exit /b 1
)
echo.

echo [4/5] 필수 패키지 간단 테스트...
python -c "import fastapi; print('FastAPI OK')"
python -c "import uvicorn; print('Uvicorn OK')"
echo.

echo [5/5] FastAPI 서버 시작...
echo.
echo 🔗 테스트 URL: http://localhost:8080/departments
echo 🔗 API 문서: http://localhost:8080/docs
echo.
echo ⚠️ 주의: 오류 메시지가 나오면 스크린샷 찍어서 보여주세요!
echo.
pause

uvicorn main:app --host 127.0.0.1 --port 8080 --reload

pause 