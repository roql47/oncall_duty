@echo off
chcp 65001 > nul
echo =========================================
echo 📋 로그 관리 시스템
echo =========================================
echo.

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo 📁 현재 디렉토리: %CD%
echo.

echo 사용 가능한 명령:
echo   1. list   - 로그 파일 목록 조회
echo   2. view   - 로그 파일 내용 조회  
echo   3. tail   - 실시간 로그 모니터링
echo   4. clean  - 오래된 로그 파일 정리
echo   5. stats  - 로그 통계 조회
echo.

if "%1"=="" (
    echo 📖 사용법:
    echo   %~nx0 list [--backend django/fastapi/system] [--type access/api/error/debug] [--days 7]
    echo   %~nx0 view ^<backend^> ^<type^> [--date 2024-01-15] [--lines 50]
    echo   %~nx0 tail ^<backend^> ^<type^> [--lines 50]
    echo   %~nx0 clean [--days 30] [--dry-run]
    echo   %~nx0 stats
    echo.
    echo 💡 예시:
    echo   %~nx0 list --backend django --days 3
    echo   %~nx0 view django api --date 2024-01-15 --lines 100
    echo   %~nx0 tail fastapi error
    echo   %~nx0 clean --days 30 --dry-run
    echo   %~nx0 stats
    echo.
    pause
    exit /b 0
)

echo 🔧 로그 관리 스크립트 실행 중...
echo.

python logs/log_manager.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 스크립트 실행 중 오류가 발생했습니다.
    echo 📞 문제가 지속되면 시스템 관리자에게 문의하세요.
) else (
    echo.
    echo ✅ 작업이 완료되었습니다.
)

echo.
pause 