# 외부 접속 시 DB 업데이트 문제 해결 가이드

## 🚨 문제 상황
다른 PC에서 접속은 되지만 **DB 업데이트가 안 되는 경우**

## 🔍 원인 분석
1. **CSRF 토큰 문제**: 외부 접속 시 Django CSRF 검증 실패
2. **CORS 설정 문제**: Cross-Origin 요청 차단
3. **패키지 누락**: django-cors-headers 패키지 미설치
4. **보안 설정**: Django 기본 보안 설정으로 인한 외부 접속 차단

## 🛠️ 해결 방법

### 1단계: 필수 패키지 설치
```batch
# 패키지 자동 설치
install_external_packages.bat
```

또는 수동 설치:
```cmd
pip install django-cors-headers
```

### 2단계: Django 설정 확인
이미 수정된 설정들:

#### `oncall_system/settings.py`
```python
# CORS 앱 추가
INSTALLED_APPS = [
    # ... 기존 앱들
    'corsheaders',  # 추가됨
    'schedule',
]

# CORS 미들웨어 추가 (최상단에 위치)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # 추가됨
    # ... 기존 미들웨어들
]

# 외부 접속 허용
ALLOWED_HOSTS = ['*']

# 동적 CSRF 신뢰 도메인
CSRF_TRUSTED_ORIGINS = [
    'http://localhost',
    'http://127.0.0.1',
    'http://localhost:*',
    'http://127.0.0.1:*',
    # IP 주소 자동 감지로 추가됨
]

# 동적 CORS 허용
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
```

### 3단계: 서버 재시작
```batch
# 기존 서버 모두 종료 후
start_all_external.bat
```

## 🔧 추가 설정 (자동 적용됨)

### 동적 IP 감지
Django 시작 시 자동으로 현재 IP 주소를 감지하여 CSRF 및 CORS 설정에 추가

### 보안 설정 완화 (개발환경)
```python
# 세션 및 CSRF 쿠키 설정
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# 디버그 모드에서 CSRF 검증 완화
if DEBUG:
    CSRF_COOKIE_HTTPONLY = False
    CSRF_USE_SESSIONS = False
```

## 🧪 테스트 방법

### 1. 패키지 설치 확인
```cmd
pip list | findstr -i cors
```
**결과**: `django-cors-headers` 패키지가 보여야 함

### 2. Django 서버 로그 확인
서버 시작 시 다음 메시지 확인:
```
🌐 외부 접속 설정 완료 - 현재 IP: [IP주소]
🔒 CSRF 신뢰 도메인: [도메인 목록]
🔄 CORS 허용 도메인: [도메인 목록]
```

### 3. 외부 접속 테스트
1. 다른 PC에서 `http://[IP주소]/` 접속
2. 일정 추가/수정 시도
3. 데이터베이스 업데이트 확인

## 🐞 문제 해결

### 여전히 DB 업데이트 안 됨
**원인**: 패키지 설치 안 됨
**해결**: 
```cmd
pip install django-cors-headers
python manage.py collectstatic --noinput
```

### CSRF 토큰 오류
**원인**: 브라우저 캐시 문제
**해결**: 
1. 브라우저 캐시 삭제 (Ctrl+F5)
2. 시크릿 모드로 접속
3. 다른 브라우저 사용

### 403 Forbidden 오류
**원인**: CORS 설정 문제
**해결**:
```python
# settings.py 끝에 추가
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
```

### 500 Internal Server Error
**원인**: 패키지 충돌
**해결**:
```cmd
pip uninstall django-cors-headers
pip install django-cors-headers
```

## 📊 Django 로그 모니터링

### 터미널에서 확인할 내용
```
Django version 5.x.x, using settings 'oncall_system.settings'
🌐 외부 접속 설정 완료 - 현재 IP: 192.168.1.100
🔒 CSRF 신뢰 도메인: ['http://localhost', 'http://127.0.0.1', 'http://192.168.1.100', ...]
🔄 CORS 허용 도메인: ['http://192.168.1.100:3000', 'http://192.168.1.100:8000', ...]
```

### 요청 로그 확인
```
[날짜] "POST /schedule/add/ HTTP/1.1" 200 - (성공)
[날짜] "POST /schedule/add/ HTTP/1.1" 403 - (CSRF 실패)
[날짜] "POST /schedule/add/ HTTP/1.1" 500 - (서버 오류)
```

## 🔒 보안 주의사항

### 개발 환경에서만 사용
```python
# 운영 환경에서는 반드시 수정 필요
ALLOWED_HOSTS = ['*']  # 특정 도메인만 허용
CORS_ALLOW_ALL_ORIGINS = True  # 특정 도메인만 허용
```

### 권장 운영 환경 설정
```python
# 운영 환경 예시
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
CORS_ALLOWED_ORIGINS = [
    "https://yourdomain.com",
    "https://www.yourdomain.com",
]
CORS_ALLOW_ALL_ORIGINS = False
```

## 📝 요약

1. **`install_external_packages.bat`** 실행
2. **Django 서버 재시작**
3. **브라우저 캐시 삭제**
4. **외부 접속 테스트**

이 단계를 따르면 외부 접속 시 DB 업데이트 문제가 해결됩니다! 🎉

---

**문제가 지속되면 Django 서버 로그를 확인하고 오류 메시지를 점검하세요.** 