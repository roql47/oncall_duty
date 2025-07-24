# 로그 시스템 가이드

## 디렉토리 구조
```
logs/
├── django/           # Django 백엔드 로그
│   ├── access/      # 접근 로그 (일별)
│   ├── api/         # API 요청 로그 (일별)
│   ├── error/       # 에러 로그 (일별)
│   └── debug/       # 디버그 로그 (일별)
├── fastapi/         # FastAPI 백엔드 로그
│   ├── access/      # 접근 로그 (일별)
│   ├── api/         # API 요청 로그 (일별)
│   ├── error/       # 에러 로그 (일별)
│   └── debug/       # 디버그 로그 (일별)
└── system/          # 시스템 통합 로그
    ├── startup/     # 시스템 시작 로그
    ├── performance/ # 성능 모니터링 로그
    └── security/    # 보안 관련 로그
```

## 로그 유형별 설명

### Django 로그
- **access**: HTTP 요청/응답 정보
- **api**: API 엔드포인트 호출 및 응답 시간
- **error**: 에러 및 예외 상황
- **debug**: 개발 및 디버깅 정보

### FastAPI 로그  
- **access**: HTTP 요청/응답 정보
- **api**: API 엔드포인트 호출 및 응답 시간
- **error**: 에러 및 예외 상황
- **debug**: 개발 및 디버깅 정보

### 시스템 로그
- **startup**: 애플리케이션 시작/종료 로그
- **performance**: 응답 시간, 메모리 사용량 등
- **security**: 인증, 권한, 보안 이벤트

## 로그 파일 명명 규칙
- 형식: `{백엔드}_{로그타입}_{YYYY-MM-DD}.txt`
- 예시: `django_api_2024-01-15.txt`, `fastapi_error_2024-01-15.txt`

## 로그 보관 정책
- 일별 로테이션
- 30일 보관 후 자동 삭제
- 에러 로그는 90일 보관 