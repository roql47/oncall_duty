# 외부 접속용 NGINX 프록시 설정 가이드

## 📋 개요
이 가이드는 다른 PC에서 당신의 컴퓨터로 접속할 수 있도록 nginx 프록시를 설정하는 방법을 설명합니다.

## 🎯 목표
- 다른 PC에서 `http://[당신의_IP_주소]/`로 접속 가능
- 모든 서비스를 단일 포트(80)로 통합
- 방화벽 설정 자동화

## 📁 생성된 파일들

### 설정 파일
- `nginx_external.conf`: 외부 접속용 nginx 설정
- `oncall_system/settings.py`: Django ALLOWED_HOSTS 수정

### 실행 스크립트
- `start_external.bat`: 외부 접속용 서비스 시작
- `start_nginx_external.bat`: 외부 접속용 nginx 시작
- `start_all_external.bat`: 모든 서비스 한 번에 시작
- `setup_firewall.bat`: 방화벽 설정 (관리자 권한 필요)

## 🚀 사용 방법

### 방법 1: 단계별 실행
```batch
# 1단계: 방화벽 설정 (관리자 권한으로 실행)
setup_firewall.bat

# 2단계: 외부 접속용 서비스 시작
start_external.bat

# 3단계: nginx 프록시 시작
start_nginx_external.bat
```

### 방법 2: 한 번에 실행 (권장)
```batch
# 1단계: 방화벽 설정 (관리자 권한으로 실행)
setup_firewall.bat

# 2단계: 전체 시스템 시작
start_all_external.bat
```

## 🌐 접속 주소

### 통합 접속 (nginx 프록시 사용)
- **메인 사이트**: `http://[당신의_IP_주소]/`
- **Django 관리자**: `http://[당신의_IP_주소]/api/admin/`
- **FastAPI 문서**: `http://[당신의_IP_주소]/chatbot/docs`

### 개별 서비스 접속
- **Django**: `http://[당신의_IP_주소]:8000`
- **FastAPI**: `http://[당신의_IP_주소]:8080`
- **React**: `http://[당신의_IP_주소]:3000`

## 📝 IP 주소 확인 방법

### Windows 명령어
```cmd
ipconfig
```

### PowerShell 명령어
```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"}
```

## 🔧 주요 변경 사항

### 1. Django 설정 수정
```python
# oncall_system/settings.py
ALLOWED_HOSTS = ['*']  # 모든 호스트 허용
```

### 2. 서비스 호스트 설정
```bash
# Django
python manage.py runserver 0.0.0.0:8000

# FastAPI
uvicorn main:app --host 0.0.0.0 --port 8080

# React
set HOST=0.0.0.0 && npm start
```

### 3. nginx 설정
```nginx
server {
    listen 80;
    server_name _;  # 모든 도메인/IP 허용
    ...
}
```

## 🔥 방화벽 설정

### 자동 설정 (권장)
```batch
# 관리자 권한으로 실행
setup_firewall.bat
```

### 수동 설정
```cmd
# 관리자 권한으로 실행
netsh advfirewall firewall add rule name="Allow HTTP (Port 80)" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="Allow Django (Port 8000)" dir=in action=allow protocol=TCP localport=8000
netsh advfirewall firewall add rule name="Allow FastAPI (Port 8080)" dir=in action=allow protocol=TCP localport=8080
netsh advfirewall firewall add rule name="Allow React (Port 3000)" dir=in action=allow protocol=TCP localport=3000
```

## 🐞 문제 해결

### 1. 외부에서 접속이 안 됨
**원인**: 방화벽이 차단하고 있음
**해결**: `setup_firewall.bat`을 관리자 권한으로 실행

### 2. nginx 시작 실패
**원인**: 포트 80이 이미 사용 중
**해결**: 
```cmd
# 포트 사용 확인
netstat -an | find "80"

# IIS 중지 (필요시)
net stop w3svc
```

### 3. 502 Bad Gateway 오류
**원인**: 백엔드 서비스가 실행되지 않음
**해결**: `start_external.bat`으로 모든 서비스 시작

### 4. Django 관리자 접속 불가
**원인**: ALLOWED_HOSTS 설정 문제
**해결**: `oncall_system/settings.py`에서 `ALLOWED_HOSTS = ['*']` 확인

### 5. React 개발 서버 외부 접속 불가
**원인**: HOST 환경변수 설정 안 됨
**해결**: `set HOST=0.0.0.0 && npm start`로 실행

## ⚠️ 보안 주의사항

### 개발 환경에서만 사용
- `ALLOWED_HOSTS = ['*']`는 개발 환경에서만 사용
- 운영 환경에서는 특정 도메인만 허용

### 방화벽 설정
- 필요한 포트만 열기
- 사용하지 않는 포트는 즉시 차단

### 네트워크 보안
- 신뢰하는 네트워크에서만 사용
- 공공 WiFi에서는 사용 금지

## 📊 성능 최적화

### nginx 설정 최적화
```nginx
# nginx_external.conf에서 수정 가능
worker_processes auto;
worker_connections 2048;
```

### 캐시 설정
```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, no-transform";
}
```

## 🔄 서비스 관리

### 서비스 중지
```cmd
# nginx 중지
nginx -s stop

# 각 서비스 중지
# 해당 창에서 Ctrl+C
```

### 설정 다시 로드
```cmd
# nginx 설정 다시 로드
nginx -s reload

# 설정 테스트
nginx -t
```

## 🎉 테스트 방법

### 1. 로컬 테스트
```
http://localhost/
```

### 2. 같은 네트워크에서 테스트
```
http://[당신의_IP_주소]/
```

### 3. 모든 기능 테스트
- 메인 페이지 로드
- Django 관리자 로그인
- FastAPI 문서 확인
- 챗봇 기능 테스트

## 📞 지원

문제가 발생하면 다음을 확인하세요:
1. 방화벽 설정 상태
2. 모든 서비스 실행 상태
3. nginx 로그 확인: `logs/error.log`
4. 네트워크 연결 상태

---

**축하합니다! 🎉 이제 다른 PC에서도 당신의 당직 시스템에 접속할 수 있습니다!** 