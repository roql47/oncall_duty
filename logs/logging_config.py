import os
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path
import json

# 프로젝트 루트 디렉토리 
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"

# 로그 디렉토리 구조 생성
LOG_DIRECTORIES = [
    "django/access",
    "django/api", 
    "django/error",
    "django/debug",
    "fastapi/access",
    "fastapi/api",
    "fastapi/error", 
    "fastapi/debug",
    "fastapi/chatbot",  # 챗봇 대화 로그 추가
    "system/startup",
    "system/performance",
    "system/security"
]

def ensure_log_directories():
    """로그 디렉토리들이 존재하는지 확인하고 생성"""
    for directory in LOG_DIRECTORIES:
        log_path = LOGS_DIR / directory
        log_path.mkdir(parents=True, exist_ok=True)
    
    print(f"✅ 로그 디렉토리 구조가 준비되었습니다: {LOGS_DIR}")

def get_log_filename(backend, log_type, date=None):
    """로그 파일명 생성"""
    if date is None:
        date = datetime.now()
    
    date_str = date.strftime('%Y-%m-%d')
    return f"{backend}_{log_type}_{date_str}.txt"

def get_log_filepath(backend, log_type, date=None):
    """로그 파일 전체 경로 생성"""
    filename = get_log_filename(backend, log_type, date)
    return LOGS_DIR / backend / log_type / filename

class CustomJSONFormatter(logging.Formatter):
    """JSON 형태로 로그를 포맷팅하는 커스텀 포매터"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # 추가 필드가 있으면 포함
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'ip_address'):
            log_entry['ip_address'] = record.ip_address
        if hasattr(record, 'method'):
            log_entry['method'] = record.method
        if hasattr(record, 'url'):
            log_entry['url'] = record.url
        if hasattr(record, 'response_time'):
            log_entry['response_time'] = record.response_time
        if hasattr(record, 'status_code'):
            log_entry['status_code'] = record.status_code
            
        return json.dumps(log_entry, ensure_ascii=False)

class TimedRotatingFileHandlerWithCleanup(logging.handlers.TimedRotatingFileHandler):
    """파일 로테이션과 오래된 로그 파일 정리를 수행하는 핸들러"""
    
    def __init__(self, filename, when='midnight', interval=1, backupCount=30, **kwargs):
        super().__init__(filename, when, interval, backupCount, **kwargs)
        self.cleanup_days = {
            'error': 90,    # 에러 로그는 90일 보관
            'security': 90, # 보안 로그는 90일 보관  
            'default': 30   # 기본 30일 보관
        }
    
    def doRollover(self):
        """로그 롤오버 시 오래된 파일들 정리"""
        super().doRollover()
        self.cleanup_old_logs()
    
    def cleanup_old_logs(self):
        """설정된 보관 기간보다 오래된 로그 파일들 삭제"""
        try:
            log_dir = Path(self.baseFilename).parent
            log_name_pattern = Path(self.baseFilename).stem
            
            # 로그 타입에 따른 보관 기간 결정
            cleanup_days = self.cleanup_days['default']
            for log_type, days in self.cleanup_days.items():
                if log_type in str(log_dir).lower():
                    cleanup_days = days
                    break
            
            cutoff_date = datetime.now() - timedelta(days=cleanup_days)
            
            # 오래된 로그 파일들 찾아서 삭제
            deleted_count = 0
            for log_file in log_dir.glob(f"{log_name_pattern}*"):
                if log_file.is_file():
                    file_date = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_date < cutoff_date:
                        log_file.unlink()
                        deleted_count += 1
            
            if deleted_count > 0:
                print(f"🗑️ {log_dir}에서 {deleted_count}개의 오래된 로그 파일을 삭제했습니다.")
                
        except Exception as e:
            print(f"❌ 로그 파일 정리 중 오류 발생: {e}")

def create_logger(name, backend, log_type, level=logging.INFO):
    """로거 생성 유틸리티"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 이미 핸들러가 있으면 중복 추가 방지
    if logger.handlers:
        return logger
    
    # 로그 파일 경로
    log_file = get_log_filepath(backend, log_type)
    
    # TimedRotatingFileHandler 설정
    handler = TimedRotatingFileHandlerWithCleanup(
        filename=str(log_file),
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    
    # JSON 포매터 적용
    formatter = CustomJSONFormatter()
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    # 콘솔 출력도 추가 (개발 환경)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

def log_api_request(logger, request_data):
    """API 요청 로깅을 위한 헬퍼 함수"""
    logger.info(
        "API 요청",
        extra={
            'request_id': request_data.get('request_id'),
            'method': request_data.get('method'),
            'url': request_data.get('url'),
            'ip_address': request_data.get('ip_address'),
            'user_agent': request_data.get('user_agent'),
            'response_time': request_data.get('response_time'),
            'status_code': request_data.get('status_code'),
            'response_size': request_data.get('response_size'),
        }
    )

def log_system_startup(backend_name, version=None):
    """시스템 시작 로그"""
    startup_logger = create_logger(f'{backend_name}_startup', 'system', 'startup')
    startup_logger.info(
        f"{backend_name} 백엔드 시작",
        extra={
            'backend': backend_name,
            'version': version,
            'pid': os.getpid(),
        }
    )

def log_performance_metric(metric_name, value, unit='ms'):
    """성능 메트릭 로깅"""
    perf_logger = create_logger('performance', 'system', 'performance')
    perf_logger.info(
        f"성능 메트릭: {metric_name}",
        extra={
            'metric_name': metric_name,
            'value': value,
            'unit': unit,
        }
    )

def log_chatbot_conversation(session_id, user_message, bot_response, response_time, ip_address=None, entities=None):
    """챗봇 대화 로깅 - 강화된 버전"""
    
    # 개인정보 마스킹 (전화번호, 주민번호 등)
    masked_message = mask_sensitive_info(user_message)
    masked_response = mask_sensitive_info(bot_response)
    
    # 콘솔에 항상 출력
    print(f"💬 챗봇 로그: 세션={session_id[:8]}... | 질문={masked_message[:50]}... | 응답={masked_response[:50]}... | {response_time:.0f}ms")
    
    # 강화된 로깅 시스템
    log_success = False
    
    try:
        # 1. 정식 로거를 통한 로깅 시도
        chatbot_logger = create_logger('fastapi_chatbot', 'fastapi', 'chatbot')
        
        # 더 자세한 로그 정보 구성
        log_data = {
            'session_id': session_id,
            'user_message': masked_message,
            'bot_response': masked_response,
            'response_time_ms': round(response_time, 2),
            'ip_address': ip_address or 'unknown',
            'message_length': len(user_message),
            'response_length': len(bot_response),
            'entities': entities or {},
            'timestamp': datetime.now().isoformat(),
        }
        
        # 로그 메시지 구성
        log_message = f"사용자: {masked_message[:100]}{'...' if len(masked_message) > 100 else ''} | 봇: {masked_response[:100]}{'...' if len(masked_response) > 100 else ''}"
        
        chatbot_logger.info(log_message, extra=log_data)
        log_success = True
        print("✅ 정식 로거를 통한 로깅 성공")
        
    except Exception as logger_error:
        print(f"⚠️ 정식 로거 실패: {logger_error}")
    
    # 2. 직접 파일 로깅 (백업)
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 여러 백업 파일에 저장
        backup_files = [
            LOGS_DIR / "fastapi" / "chatbot" / f"conversations_{today}.txt",
            LOGS_DIR / "fastapi" / "chatbot" / f"conversations_{today}.json", 
            LOGS_DIR / "fastapi" / "chatbot" / f"backup_chatbot_{today}.log",
            LOGS_DIR / "fastapi" / "chatbot" / f"fallback_{today}.txt"
        ]
        
        # 텍스트 로그 내용
        text_log_content = f"[{timestamp}] SESSION:{session_id} | USER:{masked_message} | BOT:{masked_response} | TIME:{response_time:.2f}ms | IP:{ip_address or 'unknown'} | ENTITIES:{entities or {}}\n"
        
        # JSON 로그 내용
        json_log_entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id,
            'user_message': masked_message,
            'bot_response': masked_response,
            'response_time_ms': round(response_time, 2),
            'ip_address': ip_address or 'unknown',
            'entities': entities or {},
        }
        
        files_saved = 0
        for backup_file in backup_files:
            try:
                # 디렉토리가 없으면 생성
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(backup_file, 'a', encoding='utf-8') as f:
                    if backup_file.suffix == '.json':
                        f.write(json.dumps(json_log_entry, ensure_ascii=False) + '\n')
                    else:
                        f.write(text_log_content)
                files_saved += 1
                
            except Exception as file_error:
                print(f"⚠️ 개별 백업 파일 저장 실패 {backup_file}: {file_error}")
        
        if files_saved > 0:
            print(f"✅ 직접 파일 로깅 성공: {files_saved}개 파일에 저장됨")
            log_success = True
            
    except Exception as backup_error:
        print(f"❌ 직접 파일 로깅도 실패: {backup_error}")
        import traceback
        traceback.print_exc()
    
    # 3. 최후의 수단 - 단순 텍스트 파일
    if not log_success:
        try:
            emergency_file = LOGS_DIR / "fastapi" / "chatbot" / f"emergency_{datetime.now().strftime('%Y-%m-%d')}.txt"
            emergency_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(emergency_file, 'a', encoding='utf-8') as f:
                emergency_content = f"[EMERGENCY LOG {datetime.now().isoformat()}] SESSION:{session_id} | USER:{masked_message} | BOT:{masked_response} | TIME:{response_time:.2f}ms\n"
                f.write(emergency_content)
            
            print(f"🚨 응급 로그 파일에 저장됨: {emergency_file}")
            
        except Exception as emergency_error:
            print(f"💀 모든 로깅 방법 실패: {emergency_error}")
            # 마지막 시도: 프로젝트 루트에 직접 저장
            try:
                root_emergency = Path(__file__).parent.parent / f"chatbot_emergency_{datetime.now().strftime('%Y%m%d')}.log"
                with open(root_emergency, 'a', encoding='utf-8') as f:
                    f.write(f"[FINAL EMERGENCY {datetime.now().isoformat()}] {session_id}: {masked_message} -> {masked_response}\n")
                print(f"💀 최종 응급 로그: {root_emergency}")
            except:
                print(f"💀💀 완전한 로깅 실패")

def mask_sensitive_info(text):
    """민감한 정보 마스킹"""
    import re
    
    # 전화번호 마스킹 (010-1234-5678 -> 010-****-5678)
    text = re.sub(r'(\d{2,3})-?(\d{3,4})-?(\d{4})', r'\1-****-\3', text)
    
    # 주민등록번호 마스킹 (123456-1234567 -> 123456-*******) 
    text = re.sub(r'(\d{6})-?(\d{7})', r'\1-*******', text)
    
    # 이메일 마스킹 (user@domain.com -> u***@domain.com)
    text = re.sub(r'([a-zA-Z0-9._%+-])([a-zA-Z0-9._%+-]*?)([a-zA-Z0-9._%+-])(@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', 
                  r'\1***\3\4', text)
    
    return text

# 초기화 시 디렉토리 생성 - 강화된 버전
print("🔧 로깅 시스템 초기화 중...")
try:
    ensure_log_directories()
    print("✅ 로그 디렉토리 초기화 완료")
except Exception as init_error:
    print(f"⚠️ 로그 디렉토리 초기화 오류: {init_error}")
    # 기본 디렉토리라도 생성
    try:
        chatbot_dir = LOGS_DIR / "fastapi" / "chatbot"
        chatbot_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ 최소 챗봇 로그 디렉토리는 생성됨: {chatbot_dir}")
    except Exception as minimal_error:
        print(f"❌ 최소 디렉토리 생성도 실패: {minimal_error}") 