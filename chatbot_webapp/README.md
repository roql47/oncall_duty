# 챗봇 웹앱 구조 및 실행 방법

## 폴더 구조

```
chatbot_webapp/
  ├─ frontend/         # React 프론트엔드 (카톡 스타일 챗 UI)
  ├─ backend/          # FastAPI 백엔드
  │    ├─ main.py      # 백엔드 메인 서버 코드
  │    ├─ duty_data.json # 당직의 예시 데이터
  │    └─ requirements.txt # 백엔드 패키지 목록
  └─ README.md         # 설명 파일
```

## 백엔드 실행 방법

1. Python 3.8 이상 설치
2. backend 폴더로 이동
3. 패키지 설치
   ```bash
   pip install -r requirements.txt
   ```
4. 서버 실행
   ```bash
   uvicorn main:app --reload
   ```

## 프론트엔드
- frontend 폴더에서 React 앱을 생성해 사용합니다.
- 예시:
  ```bash
  npx create-react-app frontend
  ```
- 이후 카톡 스타일 챗 UI를 구현하고, 백엔드 `/chat` 엔드포인트와 연동합니다.

## 주요 파일 설명
- `backend/main.py`: FastAPI 기반 챗봇 API 서버
- `backend/duty_data.json`: 날짜/과/역할별 당직의 예시 데이터
- `backend/requirements.txt`: 백엔드 의존성 패키지 목록

---

프론트엔드 예시 코드가 필요하면 말씀해 주세요! 