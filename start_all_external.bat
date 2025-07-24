@echo off
chcp 65001 >nul
echo ============================================
echo    외부 접속용 전체 시스템 시작
echo ============================================
echo.

echo 💻 IP 주소 확인 중...
for /f "tokens=2 delim=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    for /f "tokens=1" %%b in ("%%a") do (
        echo   - 현재 IP: %%b
    )
)

echo.
echo 🔧 외부 접속용 설정으로 전체 시스템 시작 중... (백그라운드 숨김 모드)
echo.

echo [1/4] Django 서버 시작 중... (모든 호스트 허용)
powershell -Command "Start-Process -FilePath 'cmd' -ArgumentList '/c', 'chcp 65001 >nul && python manage.py runserver 0.0.0.0:8000' -WindowStyle Hidden"
echo ✅ Django 서버 시작됨 (숨김 모드)

echo 잠시 대기 중...
timeout /t 5 /nobreak >nul

echo [2/4] FastAPI 챗봇 서버 시작 중... (모든 호스트 허용)
powershell -Command "Start-Process -FilePath 'cmd' -ArgumentList '/c', 'chcp 65001 >nul && cd chatbot_webapp\backend && uvicorn main:app --host 0.0.0.0 --port 8080 --reload' -WindowStyle Hidden"
echo ✅ FastAPI 서버 시작됨 (숨김 모드)

echo 잠시 대기 중...
timeout /t 5 /nobreak >nul

echo [3/4] React 프론트엔드 시작 중... (localhost + nginx 프록시)
powershell -Command "Start-Process -FilePath 'cmd' -ArgumentList '/c', 'chcp 65001 >nul && cd frontend && npm start' -WindowStyle Hidden"
echo ✅ React 프론트엔드 시작됨 (숨김 모드)

echo 잠시 대기 중... (백엔드 서비스 완전 시작 대기)
timeout /t 15 /nobreak >nul

echo [4/4] NGINX 프록시 서버 시작 중...
if exist nginx_external.conf (
    rem nginx가 PATH에 있는지 확인
    where nginx >nul 2>nul
    if %errorlevel% neq 0 (
        rem 로컬 nginx 폴더 확인
        if exist nginx\nginx.exe (
            echo 🔍 로컬 nginx 발견! 사용 중...
            nginx\nginx.exe -c %cd%\nginx_external.conf
            if %errorlevel% neq 0 (
                echo ❌ nginx 시작 실패!
            ) else (
                echo ✅ nginx 프록시 서버 시작됨
            )
        ) else (
            echo ⚠️  nginx가 설치되지 않았습니다.
            echo 🔧 자동 설치를 진행하시겠습니까? (Y/N)
            choice /c YN /n /t 10 /d N
            if errorlevel 2 (
                echo ⏭️  nginx 설치를 건너뜁니다.
                echo 💡 수동으로 install_nginx.bat을 실행하거나
                echo    start_nginx.bat을 실행하세요.
            ) else (
                echo 🚀 nginx 자동 설치 시작...
                call install_nginx.bat
                echo 🔄 nginx 시작 재시도...
                if exist nginx\nginx.exe (
                    nginx\nginx.exe -c %cd%\nginx_external.conf
                    if %errorlevel% neq 0 (
                        echo ❌ nginx 시작 실패!
                    ) else (
                        echo ✅ nginx 프록시 서버 시작됨
                    )
                )
            )
        )
    ) else (
        nginx -c %cd%\nginx_external.conf
        if %errorlevel% neq 0 (
            echo ❌ nginx 시작 실패!
            echo 수동으로 start_nginx.bat을 실행하세요.
        ) else (
            echo ✅ nginx 프록시 서버 시작됨
        )
    )
) else (
    echo ❌ nginx_external.conf 파일이 없습니다!
    echo 수동으로 start_nginx.bat을 실행하세요.
)

echo.
echo 🎉 외부 접속용 전체 시스템이 시작되었습니다! (백그라운드 숨김 모드)
echo.
echo 🌐 외부 접속 주소 (다른 PC에서 접속):
echo   - 메인 사이트: http://[위의_IP_주소]/
echo   - Django 관리자: http://[위의_IP_주소]/api/admin/
echo   - FastAPI 문서: http://[위의_IP_주소]/chatbot/docs
echo.
echo 📋 개별 서비스 주소:
echo   - Django 직접 접속: http://[위의_IP_주소]:8000
echo   - FastAPI 직접 접속: http://[위의_IP_주소]:8080
echo   - React 직접 접속: http://[위의_IP_주소]:3000
echo.
echo 📝 서비스 관리:
echo   - nginx 중지: nginx -s stop
echo   - nginx 재시작: nginx -s reload
echo   - 프로세스 확인: 작업 관리자에서 확인
echo   - 프로세스 종료: 작업 관리자에서 종료 (cmd창이 보이지 않음)
echo.
echo 🔥 방화벽 설정이 안 되어 있다면:
echo   setup_firewall.bat을 관리자 권한으로 실행하세요.
echo.
echo 💡 테스트 방법:
echo   1. 위의 IP 주소를 확인하세요
echo   2. 다른 PC에서 http://[IP주소]로 접속하세요
echo   3. 모든 기능이 정상 작동하는지 확인하세요
echo.
echo ⚠️  주의사항: 
echo   - 모든 서비스가 숨김 모드로 실행되므로 CMD 창이 보이지 않습니다
echo   - 작업 관리자에서 python.exe, node.exe, nginx.exe 프로세스를 확인할 수 있습니다
echo   - 서비스 종료는 작업 관리자에서 해당 프로세스를 종료하세요
echo.
echo 🚀 모든 서비스가 백그라운드에서 숨김 모드로 실행 중입니다!
timeout /t 5 /nobreak >nul
start http://localhost

echo.
echo ============================================
echo 이 창은 닫아도 됩니다. 모든 서비스가 숨김 모드로 계속 실행됩니다.
echo ============================================
pause 