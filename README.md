# 당직 스케줄 시스템

이 프로젝트는 병원 의사들의 당직 스케줄을 관리하고 조회할 수 있는 웹 애플리케이션입니다.

## 기능

- 월간 당직 일정 조회
- 부서별 일정 조회
- 의사별 일정 조회
- 관리자 페이지를 통한 일정 관리
- 지정된 부서 목록에서 선택 (드롭다운)
- 근무 시간대 관리

## 모델 구조

- **Department(부서)**: 지정된 부서 목록에서 선택할 수 있는 드롭다운 제공
- **Doctor(의사)**: 의사 정보 및 소속 부서 관리
- **TimeSlot(시간대)**: 일정의 시간대 정보 관리
- **WorkSchedule(근무시간)**: 근무 시간대 설정 (시작 시간, 종료 시간, 설명)
- **Schedule(일정)**: 의사, 근무시간, 당직 여부 등 관리

## 지원하는 부서 목록

- 순환기내과
- 순환기내과 병동
- 분과통합(순환기내과 제외)
- 내과계 중환자실
- 소화기내과 응급내시경(on call)
- 외과(ER call only)
- 외과 당직의
- 외과 수술의
- 외과계 중환자실
- 산부인과
- 소아과 ER
- 소아과 병동
- 소아과 NICU
- 신경과
- 신경외과
- 정형외과
- 재활의학과
- 성형외과
- 폐식도외과
- 심장혈관외과
- 비뇨의학과
- 이비인후과(on call)
- 마취통증의학과
- 응급의학과

## 시작하기

### 필수 조건

- Python 3.8 이상
- Django 5.0 이상

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

6. 개발 서버를 실행합니다.
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

## 배포

이 애플리케이션은 Django 프레임워크로 작성되었으며, Django 공식 배포 가이드를 참고하여 배포할 수 있습니다.

## 모바일 앱 개발 계획

추후 React Native를 이용하여 모바일 앱 버전을 개발할 예정입니다. 웹 애플리케이션의 API를 활용하여 동일한 기능을 모바일에서도 사용할 수 있게 할 계획입니다. 