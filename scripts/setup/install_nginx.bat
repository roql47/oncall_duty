@echo off
chcp 65001 >nul
echo ============================================
echo    NGINX 자동 설치 스크립트
echo ============================================
echo.

echo 🔍 nginx 확인 중...
where nginx >nul 2>nul
if %errorlevel% equ 0 (
    echo ✅ nginx가 이미 설치되어 있습니다!
    nginx -v
    echo.
    echo 설치를 계속하시겠습니까? (Y/N)
    choice /c YN /n
    if errorlevel 2 goto :end
)

echo.
echo 📥 nginx 다운로드 중...
echo   - 다운로드 위치: https://nginx.org/download/nginx-1.24.0.zip
echo   - 설치 위치: %cd%\nginx\

if not exist nginx (
    mkdir nginx
)

cd nginx

echo.
echo 🌐 PowerShell을 사용하여 nginx 다운로드 중...
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://nginx.org/download/nginx-1.24.0.zip' -OutFile 'nginx.zip'}"

if exist nginx.zip (
    echo ✅ 다운로드 완료!
    
    echo.
    echo 📂 압축 해제 중...
    powershell -Command "Expand-Archive -Path 'nginx.zip' -DestinationPath '.' -Force"
    
    if exist nginx-1.24.0 (
        echo ✅ 압축 해제 완료!
        
        echo.
        echo 📁 파일 이동 중...
        xcopy nginx-1.24.0\* . /E /Y >nul
        rmdir /S /Q nginx-1.24.0 >nul
        del nginx.zip >nul
        
        echo ✅ nginx 설치 완료!
        echo.
        echo 📍 설치 위치: %cd%
        echo.
        
        echo 🔧 PATH 환경변수 추가 중...
        setx PATH "%PATH%;%cd%" >nul
        if %errorlevel% equ 0 (
            echo ✅ PATH 추가 완료! (새 cmd 창에서 적용됨)
        ) else (
            echo ⚠️  PATH 추가 실패. 수동으로 추가하세요:
            echo     %cd%
        )
        
        echo.
        echo 🧪 nginx 테스트...
        .\nginx.exe -v
        if %errorlevel% equ 0 (
            echo ✅ nginx 설치가 성공적으로 완료되었습니다!
            echo.
            echo 💡 사용법:
            echo   - 시작: nginx
            echo   - 중지: nginx -s stop  
            echo   - 재시작: nginx -s reload
            echo   - 설정 테스트: nginx -t
        ) else (
            echo ❌ nginx 테스트 실패
        )
    ) else (
        echo ❌ 압축 해제 실패
    )
) else (
    echo ❌ 다운로드 실패
    echo.
    echo 수동 설치 방법:
    echo 1. https://nginx.org/en/download.html 방문
    echo 2. Windows 버전 다운로드
    echo 3. 압축 해제 후 현재 폴더의 nginx\ 에 복사
    echo 4. nginx\nginx.exe가 있는지 확인
)

cd..

:end
echo.
echo ============================================
echo 설치 완료! 새 cmd 창을 열고 다시 시도하세요.
echo ============================================
pause 