@echo off
echo ============================================
echo    NGINX 리버스 프록시 서버 시작
echo ============================================
echo.

echo 📋 현재 설정:
echo   - 프론트엔드: http://localhost/ (React - 포트 3000)
echo   - Django API: http://localhost/api/ (포트 8000)
echo   - 챗봇 API: http://localhost/chatbot/ (포트 8080)
echo   - 관리자: http://localhost/api/admin/
echo.

echo 🔧 nginx 설정 파일 확인 중...
if not exist nginx.conf (
    echo ❌ nginx.conf 파일이 없습니다!
    echo 설정 파일을 먼저 생성하세요.
    pause
    exit /b 1
)

echo ✅ nginx.conf 파일 발견
echo.

echo 🚀 nginx 시작 중...
echo.
echo 💡 주의사항:
echo   - 이 스크립트 실행 전에 모든 백엔드 서비스가 실행되어야 합니다
echo   - start_all.bat을 먼저 실행하세요
echo.

echo nginx 시작 명령어:
echo   nginx -c %cd%\nginx.conf
echo.

echo 시작하려면 아무 키나 누르세요...
pause >nul

nginx -c %cd%\nginx.conf

if %errorlevel% neq 0 (
    echo ❌ nginx 시작에 실패했습니다!
    echo.
    echo 가능한 원인:
    echo   1. nginx가 설치되지 않음
    echo   2. 포트 80이 이미 사용 중
    echo   3. 백엔드 서비스가 실행되지 않음
    echo.
    echo nginx 중지 명령어: nginx -s stop
    echo nginx 재시작 명령어: nginx -s reload
    pause
    exit /b 1
)

echo ✅ nginx가 성공적으로 시작되었습니다!
echo.
echo 🌐 접속 주소:
echo   - 메인 사이트: http://localhost/
echo   - Django 관리자: http://localhost/api/admin/
echo   - FastAPI 문서: http://localhost/chatbot/docs
echo.
echo 📝 nginx 관리 명령어:
echo   - 중지: nginx -s stop
echo   - 재시작: nginx -s reload
echo   - 설정 테스트: nginx -t
echo.
echo 이 창은 닫아도 됩니다. nginx는 백그라운드에서 계속 실행됩니다.
pause 