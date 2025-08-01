@echo off
echo ============================================
echo    외부 접속을 위한 패키지 설치
echo ============================================
echo.

echo 🔧 Django CORS 헤더 패키지 설치 중...
pip install django-cors-headers

if %errorlevel% neq 0 (
    echo ❌ django-cors-headers 설치 실패!
    echo.
    echo 가능한 해결방법:
    echo   1. pip install --upgrade pip
    echo   2. pip install django-cors-headers --user
    echo   3. python -m pip install django-cors-headers
    echo.
    pause
    exit /b 1
)

echo ✅ django-cors-headers 설치 완료!
echo.

echo 📋 설치된 패키지 확인:
pip list | findstr -i cors
pip list | findstr -i django

echo.
echo 🎯 패키지 설치 완료!
echo.
echo 📝 다음 단계:
echo   1. Django 서버 재시작
echo   2. start_all_external.bat 실행
echo   3. 외부 접속 테스트
echo.
echo 💡 참고:
echo   - Django 설정이 자동으로 현재 IP 주소를 감지합니다
echo   - CSRF 및 CORS 설정이 동적으로 적용됩니다
echo.
pause 