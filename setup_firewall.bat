@echo off
echo ============================================
echo    방화벽 설정 (관리자 권한 필요)
echo ============================================
echo.

echo 🔥 Windows 방화벽에서 포트 허용 설정 중...
echo.

echo 📝 허용할 포트 목록:
echo   - 포트 80: nginx 프록시 서버
echo   - 포트 8000: Django 백엔드
echo   - 포트 8080: FastAPI 챗봇
echo   - 포트 3000: React 프론트엔드
echo.

echo 🔧 방화벽 규칙 추가 중...
echo.

echo [1/4] 포트 80 (HTTP) 허용 중...
netsh advfirewall firewall add rule name="Allow HTTP (Port 80)" dir=in action=allow protocol=TCP localport=80
if %errorlevel% neq 0 (
    echo ❌ 포트 80 허용 실패!
) else (
    echo ✅ 포트 80 허용 성공!
)
echo.

echo [2/4] 포트 8000 (Django) 허용 중...
netsh advfirewall firewall add rule name="Allow Django (Port 8000)" dir=in action=allow protocol=TCP localport=8000
if %errorlevel% neq 0 (
    echo ❌ 포트 8000 허용 실패!
) else (
    echo ✅ 포트 8000 허용 성공!
)
echo.

echo [3/4] 포트 8080 (FastAPI) 허용 중...
netsh advfirewall firewall add rule name="Allow FastAPI (Port 8080)" dir=in action=allow protocol=TCP localport=8080
if %errorlevel% neq 0 (
    echo ❌ 포트 8080 허용 실패!
) else (
    echo ✅ 포트 8080 허용 성공!
)
echo.

echo [4/4] 포트 3000 (React) 허용 중...
netsh advfirewall firewall add rule name="Allow React (Port 3000)" dir=in action=allow protocol=TCP localport=3000
if %errorlevel% neq 0 (
    echo ❌ 포트 3000 허용 실패!
) else (
    echo ✅ 포트 3000 허용 성공!
)
echo.

echo 🎯 방화벽 설정 완료!
echo.
echo 📊 현재 방화벽 규칙 확인:
netsh advfirewall firewall show rule name="Allow HTTP (Port 80)"
echo.
netsh advfirewall firewall show rule name="Allow Django (Port 8000)"
echo.
netsh advfirewall firewall show rule name="Allow FastAPI (Port 8080)"
echo.
netsh advfirewall firewall show rule name="Allow React (Port 3000)"
echo.

echo 🌐 외부 접속 준비 완료!
echo.
echo 다음 단계:
echo   1. start_external.bat 실행
echo   2. start_nginx_external.bat 실행
echo   3. 다른 PC에서 접속 테스트
echo.
pause 