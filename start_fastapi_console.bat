@echo off
chcp 65001 >nul
echo ============================================
echo    FastAPI 서버 시작 (콘솔 로그 표시)
echo ============================================
echo.

echo 🚀 FastAPI 챗봇 서버를 시작합니다...
echo 📋 모든 로그가 이 창에 표시됩니다.
echo 🛑 서버 종료: Ctrl+C
echo.

cd chatbot_webapp\backend
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

pause 