# 당직 스케줄 시스템

이 프로젝트는 병원 의사들의 당직 스케줄을 관리하고 조회할 수 있는 웹 애플리케이션입니다.

## 기능

- 월간 당직 일정 조회
- 부서별 일정 조회
- 의사별 일정 조회
- 관리자 페이지를 통한 일정 관리
- 지정된 부서 목록에서 선택 (드롭다운)
- 근무 시간대 관리
- 챗봇을 통한 자연어 질의응답 당직 정보 검색

## 모델 구조

- **Department(부서)**: 지정된 부서 목록에서 선택할 수 있는 드롭다운 제공
- **Doctor(의사)**: 의사 정보 및 소속 부서 관리
- **TimeSlot(시간대)**: 일정의 시간대 정보 관리
- **WorkSchedule(근무시간)**: 근무 시간대 설정 (시작 시간, 종료 시간, 설명)
- **Schedule(일정)**: 의사, 근무시간, 당직 여부 등 관리

## 시스템 아키텍처

이 시스템은 다음과 같은 세 가지 주요 컴포넌트로 구성되어 있습니다:

1. **Django 백엔드 서버 (8000 포트)**: 메인 애플리케이션 로직, 데이터베이스 관리 및 일반 웹 인터페이스 제공
2. **FastAPI 챗봇 서버 (8080 포트)**: 벡터 검색 기반 자연어 질의응답 API 및 기본 챗봇 인터페이스 제공
3. **React 프론트엔드 (3000 포트)**: 모던 UI/UX를 갖춘 사용자 인터페이스 제공 (개발 모드)

## 서버 실행 방법

### 🚀 전체 시스템 실행 (권장)
```bash
# 모든 서버를 한 번에 실행
start_all.bat
```

### 🔧 개별 서버 실행

#### FastAPI 챗봇 서버만 실행
```bash
# 기본 FastAPI 서버 시작 (권장)
start_fastapi.bat

# 안전 모드로 시작 (로깅 문제 발생 시)
start_fastapi_safe.bat
```

#### Django 서버만 실행
```bash
# Django 서버만 실행 (포트 8000)
python manage.py runserver
```

#### React 프론트엔드만 실행
```bash
# React 개발 서버만 실행 (포트 3000)
cd frontend
npm start
```

### ⚠️ 중요 사항
- **React 챗봇 사용 시**: FastAPI 서버(8080 포트)가 반드시 실행되어야 합니다.
- **로딩 문제 해결**: React 앱에서 계속 로딩 중이라면 FastAPI 서버가 실행되지 않았을 가능성이 높습니다.
- **연결 확인**: http://localhost:8080 에서 FastAPI 서버 상태를 확인할 수 있습니다.

### 🔧 문제 해결

#### React 앱에서 계속 로딩되는 문제
1. **FastAPI 서버 확인**:
   - `start_fastapi.bat` 실행
   - http://localhost:8080/departments 접속하여 서버 응답 확인

2. **로깅 시스템 문제**:
   - `start_fastapi_safe.bat` 사용 (안전 모드)
   - 로그 디렉토리 권한 확인: `logs/fastapi/chatbot/`

3. **패키지 설치 문제**:
   ```bash
   pip install fastapi uvicorn sentence-transformers faiss-cpu django
   ```

4. **포트 충돌**:
   - 다른 프로그램이 8080 포트 사용 중인지 확인
   - 작업 관리자에서 기존 서버 프로세스 종료

#### 연결 상태 확인 방법
- **FastAPI 서버**: http://localhost:8080/docs
- **부서 목록 API**: http://localhost:8080/departments  
- **React 앱**: http://localhost:3000

## 챗봇 기능

자연어로 당직 정보를 검색할 수 있는 챗봇 기능을 제공합니다. FAISS 벡터 임베딩 검색 기술을 활용하여 정확한 응답을 제공합니다.

### 챗봇 주요 기능
- 특정 날짜와 부서의 당직 정보 조회 (예: "오늘 순환기내과 당직 누구야?")
- 특정 시간대의 당직 의사 조회 (예: "내일 14시 정형외과 당직의는?")
- 당직 의사의 연락처 정보 조회 (예: "정형외과 당직의 번호는?")
- 전체 당직표 조회 (예: "5월 10일 순환기내과 당직표 알려줘")

### 챗봇 로깅 시스템

모든 챗봇 대화는 자동으로 로깅되어 관리 및 분석에 활용됩니다.

#### 로그 저장 위치
- **기본 로그**: `logs/fastapi/chatbot/fastapi_chatbot_YYYY-MM-DD.log`
- **대화 상세 로그**: `logs/fastapi/chatbot/conversations_YYYY-MM-DD.json`
- **대체 로그**: `logs/fastapi/chatbot/fallback_YYYY-MM-DD.txt` (로깅 실패 시)

#### 로깅되는 정보
- 사용자 질문 및 봇 응답 (개인정보 마스킹 처리)
- 세션 ID 및 요청 시간
- 클라이언트 IP 주소 및 브라우저 정보
- 응답 시간 및 성능 메트릭  
- 요청 소스 (React 프론트엔드, Django 템플릿 등)
- 추출된 엔티티 정보 (날짜, 부서명, 역할 등)

#### 개인정보 보호
- 전화번호, 주민등록번호 등 민감한 정보는 자동으로 마스킹 처리
- 로그 파일은 30일 후 자동 삭제 (보안 관련 로그는 90일)
- 로그 접근 권한은 시스템 관리자로 제한

#### 로깅 테스트
챗봇 로깅이 정상적으로 작동하는지 테스트하려면:
```bash
python test_chatbot_logging.py
```

### 챗봇 기술 스택
- FastAPI: 경량 API 서버
- FAISS: 페이스북 AI 연구소에서 개발한 고성능 벡터 검색 라이브러리
- SentenceTransformer: 문장 임베딩 생성 모델
- Django ORM: 직접 데이터베이스 조회를 위한 ORM 활용

## 시작하기

### 필수 조건

- Python 3.8 이상
- Django 5.0 이상
- FastAPI (챗봇 기능 사용 시)
- FAISS (챗봇 기능 사용 시)
- SentenceTransformer (챗봇 기능 사용 시)
- Node.js 18 이상 (React 프론트엔드 사용 시)

### 설치

1. 저장소를 클론합니다.
   ```
   git clone https://github.com/yourusername/oncall_system.git
   cd oncall_system
   ```

2. 가상 환경을 생성하고 활성화합니다.
   ```
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. 의존성을 설치합니다.
   ```
   pip install -r requirements.txt
   ```

4. 데이터베이스를 마이그레이션합니다.
   ```
   python manage.py makemigrations
   python manage.py migrate
   ```

5. 관리자 계정을 생성합니다.
   ```
   python manage.py createsuperuser
   ```

6. Django 개발 서버를 실행합니다.
   ```
   python manage.py runserver
   ```

7. 웹 브라우저에서 다음 주소로 접속합니다.
   ```
   http://127.0.0.1:8000/
   ```

8. 관리자 페이지에 접속하여 데이터를 추가합니다.
   ```
   http://127.0.0.1:8000/admin/
   ```

9. 챗봇 서버를 실행합니다 (별도 터미널에서).
   ```
   cd chatbot_webapp/backend
   uvicorn main:app --host 127.0.0.1 --port 8080 --reload
   ```

10. (선택사항) React 프론트엔드를 실행합니다 (별도 터미널에서).
    ```
    cd frontend
    npm install
    npm start
    ```

11. 챗봇 초기화 및 벡터 DB 업데이트를 위해 다음 URL에 접속합니다.
    ```
    http://127.0.0.1:8080/update-vectors
    ```

## 챗봇 사용하기

다음 인터페이스를 통해 챗봇을 사용할 수 있습니다:

1. **기본 챗봇 인터페이스**: `http://127.0.0.1:8080/`
   - FastAPI 서버가 제공하는 기본 챗봇 UI입니다.

2. **모던 UI 챗봇 인터페이스**: `http://localhost:3000/`
   - React 프론트엔드가 제공하는 개선된 UI를 갖춘 챗봇 인터페이스입니다.

자연어로 질문을 입력합니다. 예시:
   - "오늘 순환기내과 당직 누구야?"
   - "내일 정형외과 당직표 알려줘"
   - "5월 10일 오전 10시 소아과 당직의는?"
   - "정형외과 당직의 연락처 좀 알려줘"

## 배포

이 애플리케이션은 여러 컴포넌트로 구성되어 있어, 각각 별도로 배포해야 합니다:

1. **Django 백엔드**: Django 공식 배포 가이드를 참고하여 WSGI 서버(예: Gunicorn)와 함께 배포합니다.
2. **FastAPI 챗봇 서버**: Uvicorn 또는 Gunicorn을 사용하여 배포합니다.
3. **React 프론트엔드**: 정적 파일로 빌드한 후, Nginx 또는 CDN을 통해 제공합니다.

각 서비스는 프록시 서버(예: Nginx)를 통해 단일 도메인에서 제공할 수 있습니다.

## 모바일 앱 개발 계획

추후 React Native를 이용하여 모바일 앱 버전을 개발할 예정입니다. 웹 애플리케이션의 API와 챗봇 기능을 활용하여 동일한 기능을 모바일에서도 사용할 수 있게 할 계획입니다. 