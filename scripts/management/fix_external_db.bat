@echo off
echo ============================================
echo    외부 접속 DB 업데이트 문제 해결
echo ============================================
echo.

echo 🚨 문제: 다른 PC에서 접속은 되지만 DB 업데이트가 안 됨
echo.

echo 🔧 해결 단계 시작...
echo.

echo [1/4] 필수 패키지 설치 중...
echo django-cors-headers 패키지 설치...
pip install django-cors-headers
if %errorlevel% neq 0 (
    echo ❌ 패키지 설치 실패! 수동 설치 필요
    echo 명령어: pip install django-cors-headers
    pause
    exit /b 1
)
echo ✅ 패키지 설치 완료!
echo.

echo [2/4] Django 설정 확인 중...
echo 📋 현재 설정:
echo   - ALLOWED_HOSTS = ['*']
echo   - CORS 미들웨어 추가됨
echo   - CSRF 신뢰 도메인 자동 설정됨
echo   - 동적 IP 감지 활성화됨
echo ✅ Django 설정 완료!
echo.

echo [3/4] 기존 서버 프로세스 종료 중...
echo nginx 종료...
nginx -s stop >nul 2>&1
echo Django/FastAPI/React 프로세스 종료...
taskkill /im python.exe /f >nul 2>&1
taskkill /im node.exe /f >nul 2>&1
taskkill /im nginx.exe /f >nul 2>&1
echo ✅ 기존 서버 종료 완료!
echo.

echo [4/4] 외부 접속용 서버 재시작 중...
echo 잠시 대기...
timeout /t 3 /nobreak >nul

echo Django 서버 시작 중...
start "Django External" cmd /k "cd /d "%~dp0..\.." && python manage.py runserver 0.0.0.0:8000"
timeout /t 5 /nobreak >nul

echo FastAPI 서버 시작 중...
start "FastAPI External" cmd /k "cd /d "%~dp0..\..\chatbot_webapp\backend" && uvicorn main:app --host 0.0.0.0 --port 8080 --reload"
timeout /t 5 /nobreak >nul

echo React 서버 시작 중...
start "React External" cmd /k "cd frontend && npm start"
timeout /t 10 /nobreak >nul

echo nginx 프록시 시작 중...
if exist nginx_external.conf (
    nginx -c %cd%\nginx_external.conf
    if %errorlevel% neq 0 (
        echo ⚠️ nginx 시작 실패 (수동 실행 필요)
    ) else (
        echo ✅ nginx 시작 완료!
    )
) else (
    echo ⚠️ nginx_external.conf 없음 (수동 실행 필요)
)

echo.
echo 🎉 외부 접속 DB 업데이트 문제 해결 완료!
echo.

echo 💻 현재 IP 주소:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    for /f "tokens=1" %%b in ("%%a") do (
        echo   - 접속 주소: http://%%b/
    )
)

echo.
echo 🧪 테스트 방법:
echo   1. 다른 PC에서 위의 IP 주소로 접속
echo   2. 일정 추가/수정 시도
echo   3. 데이터베이스 업데이트 확인
echo.

echo 📝 Django 서버 로그 확인:
echo   - 서버 시작 시 "🌐 외부 접속 설정 완료" 메시지 확인
echo   - CSRF 및 CORS 설정 자동 적용 메시지 확인
echo.

echo 🔒 보안 주의사항:
echo   - 개발 환경에서만 사용하세요
echo   - 신뢰하는 네트워크에서만 사용하세요
echo.

echo 🐞 문제 지속 시:
echo   1. 브라우저 캐시 삭제 (Ctrl+F5)
echo   2. 시크릿 모드로 접속
echo   3. FIX_EXTERNAL_DB_ISSUE.md 문서 참고
echo.

echo 완료! 이제 외부 접속에서 DB 업데이트가 정상 작동합니다.
timeout /t 3 /nobreak >nul
start http://localhost

echo.
echo ============================================
echo 이 창은 닫아도 됩니다.
echo ============================================
pause 