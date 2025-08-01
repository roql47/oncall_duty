@echo off
echo ============================================
echo    당직 시스템 전체 서버 시작
echo ============================================
echo.

echo [1/3] Django 서버 시작 중... (포트 8000, 네트워크 접근 허용)
start "Django Server" cmd /k "cd /d "%~dp0..\.." && python manage.py runserver 0.0.0.0:8000"

echo 잠시 대기 중...
timeout /t 3 /nobreak >nul

echo [2/3] FastAPI 챗봇 서버 시작 중... (포트 8080, 네트워크 접근 허용)
start "FastAPI Server" cmd /k "cd /d "%~dp0..\..\chatbot_webapp\backend" && uvicorn main:app --host 0.0.0.0 --port 8080 --reload"

echo 잠시 대기 중...
timeout /t 3 /nobreak >nul

echo [3/3] React 프론트엔드 시작 중... (포트 3000)
start "React Frontend" cmd /k "cd /d "%~dp0..\..\frontend" && npm start"

echo.
echo ✅ 모든 서버가 시작되었습니다!
echo.
echo 📱 접속 주소:
echo   [로컬 접속]
echo   - React 챗봇:     http://localhost:3000
echo   - FastAPI 챗봇:   http://localhost:8080
echo   - Django 관리:    http://localhost:8000/admin
echo.
echo   [네트워크 접속]
echo   - React 챗봇:     http://10.20.30.215:3000
echo   - FastAPI 챗봇:   http://10.20.30.215:8080
echo   - Django 관리:    http://10.20.30.215:8000/admin
echo.
echo 💡 팁:
echo   - 서버를 종료하려면 각 창에서 Ctrl+C를 누르세요
echo   - 모든 창을 닫으려면 작업 관리자를 사용하세요
echo.
echo 🚀 모든 서버가 준비되면 브라우저가 자동으로 열립니다...
timeout /t 10 /nobreak >nul
start http://localhost:3000

echo.
echo ============================================
echo 이 창은 닫아도 됩니다. 서버들은 계속 실행됩니다.
echo ============================================
pause 