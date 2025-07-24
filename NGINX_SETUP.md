# NGINX 리버스 프록시 설정

## 📋 개요
이 설정은 nginx를 리버스 프록시로 사용하여 모든 서비스를 단일 포트(80)로 통합합니다.

## 🌐 서비스 구성
- **React 프론트엔드**: `http://localhost/` (포트 3000 → 80)
- **Django API**: `http://localhost/api/` (포트 8000 → 80)
- **FastAPI 챗봇**: `http://localhost/chatbot/` (포트 8080 → 80)
- **Django 관리자**: `http://localhost/api/admin/`

## 📁 생성된 파일들
- `nginx.conf`: nginx 설정 파일
- `start_nginx.bat`: nginx 시작 스크립트
- `stop_nginx.bat`: nginx 중지 스크립트

## 🚀 사용 방법

### 1. 전체 시스템 시작
```bash
# 1단계: 모든 백엔드 서비스 시작
start_all.bat

# 2단계: nginx 프록시 서버 시작
start_nginx.bat
```

### 2. nginx만 시작/중지
```bash
# nginx 시작
start_nginx.bat

# nginx 중지
stop_nginx.bat
```

### 3. 수동 nginx 명령어
```bash
# 설정 테스트
nginx -t

# nginx 시작
nginx -c %cd%\nginx.conf

# nginx 중지
nginx -s stop

# 설정 다시 로드
nginx -s reload
```

## 📝 주의사항

1. **실행 순서**: 반드시 `start_all.bat`을 먼저 실행한 후 `start_nginx.bat`을 실행하세요.

2. **포트 충돌**: 포트 80이 이미 사용 중이면 nginx 시작이 실패합니다.
   - IIS나 다른 웹 서버가 실행 중이지 않은지 확인하세요.

3. **백엔드 서비스**: nginx는 백엔드 서비스들이 정상적으로 실행되고 있을 때만 제대로 동작합니다.

## 🔧 설정 수정

### 포트 변경
`nginx.conf` 파일에서 아래 부분을 수정하세요:
```nginx
server {
    listen 80;  # 이 부분을 원하는 포트로 변경
    server_name localhost;
    ...
}
```

### 백엔드 서비스 포트 변경
`nginx.conf` 파일에서 upstream 부분을 수정하세요:
```nginx
upstream django_backend {
    server 127.0.0.1:8000;  # Django 포트
}

upstream fastapi_backend {
    server 127.0.0.1:8080;  # FastAPI 포트
}

upstream react_frontend {
    server 127.0.0.1:3000;  # React 포트
}
```

## 🐞 문제 해결

### nginx 시작 실패
1. nginx가 설치되어 있는지 확인
2. 포트 80이 사용 중인지 확인: `netstat -an | find "80"`
3. 백엔드 서비스들이 실행 중인지 확인

### 502 Bad Gateway 오류
- 백엔드 서비스가 실행되지 않은 경우 발생
- `start_all.bat`을 실행하여 모든 서비스를 시작하세요

### 403 Forbidden 오류
- 파일 권한 문제이거나 경로 설정 오류
- nginx 설정 파일의 경로를 확인하세요

## 📊 로그 확인
nginx 로그는 다음 위치에서 확인할 수 있습니다:
- 접근 로그: `logs/access.log`
- 오류 로그: `logs/error.log`

## 🔄 자동화 방법
모든 서비스를 한 번에 시작하는 통합 스크립트를 만들고 싶다면:

```batch
# start_all_with_nginx.bat
@echo off
call start_all.bat
timeout /t 10 /nobreak >nul
call start_nginx.bat
``` 