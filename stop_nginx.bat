@echo off
echo ============================================
echo    NGINX 서버 중지
echo ============================================
echo.

echo 🛑 nginx 중지 중...
nginx -s stop

if %errorlevel% neq 0 (
    echo ❌ nginx 중지에 실패했습니다!
    echo.
    echo 가능한 원인:
    echo   1. nginx가 실행되지 않음
    echo   2. nginx 프로세스가 응답하지 않음
    echo.
    echo 강제 종료를 시도하시겠습니까? (Y/N)
    set /p choice=
    if /i "%choice%"=="Y" (
        echo 강제 종료 중...
        taskkill /im nginx.exe /f
        if %errorlevel% neq 0 (
            echo ❌ nginx 프로세스를 찾을 수 없습니다.
        ) else (
            echo ✅ nginx가 강제 종료되었습니다.
        )
    )
) else (
    echo ✅ nginx가 성공적으로 중지되었습니다!
)

echo.
echo 완료!
pause 