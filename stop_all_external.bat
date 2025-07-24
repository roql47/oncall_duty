@echo off
chcp 65001 >nul
echo ============================================
echo    외부 접속용 전체 시스템 종료
echo ============================================
echo.

echo 🛑 실행 중인 서비스들을 종료합니다...
echo.

echo [1/4] Django 서버 종료 중...
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo table /nh ^| findstr runserver') do (
    taskkill /PID %%i /F >nul 2>&1
    if !errorlevel! equ 0 (
        echo ✅ Django 서버 종료됨 (PID: %%i)
    )
)

echo [2/4] FastAPI 서버 종료 중...
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo table /nh ^| findstr uvicorn') do (
    taskkill /PID %%i /F >nul 2>&1
    if !errorlevel! equ 0 (
        echo ✅ FastAPI 서버 종료됨 (PID: %%i)
    )
)

echo [3/4] React 프론트엔드 종료 중...
taskkill /F /IM node.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ React 프론트엔드 종료됨
) else (
    echo ⚠️  React 프론트엔드가 실행 중이지 않거나 이미 종료됨
)

echo [4/4] NGINX 프록시 서버 종료 중...
taskkill /F /IM nginx.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ NGINX 서버 종료됨
) else (
    echo ⚠️  NGINX가 실행 중이지 않거나 이미 종료됨
)

echo.
echo 🎉 모든 외부 접속용 서비스가 종료되었습니다!
echo.
echo 📋 확인 방법:
echo   - 작업 관리자에서 python.exe, node.exe, nginx.exe 프로세스 확인
echo   - 웹 브라우저에서 서비스 접속 불가능한지 확인
echo.
echo ============================================
echo 서비스 종료가 완료되었습니다.
echo ============================================
pause 