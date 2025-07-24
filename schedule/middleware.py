from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
import threading
import time
import uuid
import sys
import os

# 로깅 시스템 임포트
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from logs.logging_config import create_logger, log_api_request

# 스레드 로컬 저장소 (요청별 데이터 저장)
_thread_local = threading.local()

class CurrentDateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # 현재 날짜를 한국 시간 기준으로 설정
        self.current_date = timezone.now().date()

    def __call__(self, request):
        # 현재 날짜를 요청 객체에 추가
        request.current_date = self.current_date
        response = self.get_response(request)
        return response

class RequestLoggingMiddleware:
    """Django 요청 로깅 미들웨어"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # 로거 생성
        self.access_logger = create_logger('django_access', 'django', 'access')
        self.api_logger = create_logger('django_api', 'django', 'api')
        self.error_logger = create_logger('django_error', 'django', 'error')
        
        # 로깅에서 제외할 경로들
        self.exclude_paths = [
            '/static/',
            '/favicon.ico',
            '/admin/jsi18n/',
        ]
        
        print("✅ Django 요청 로깅 미들웨어가 초기화되었습니다.")
    
    def __call__(self, request):
        # 요청 시작 시간 및 고유 ID 생성
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 스레드 로컬에 요청 정보 저장
        _thread_local.request_id = request_id
        _thread_local.start_time = start_time
        
        # 요청 정보 추출
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        method = request.method
        url = request.get_full_path()
        
        # 제외 경로 체크
        should_log = not any(exclude in url for exclude in self.exclude_paths)
        
        if should_log:
            # 접근 로그 기록
            self.access_logger.info(
                f"요청 시작: {method} {url}",
                extra={
                    'request_id': request_id,
                    'method': method,
                    'url': url,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'timestamp': timezone.now().isoformat(),
                }
            )
        
        response = None
        try:
            # 실제 뷰 처리
            response = self.get_response(request)
            
            if should_log:
                # API 요청 로그 기록
                response_time = (time.time() - start_time) * 1000  # ms 단위
                
                # API 엔드포인트 판별 (JSON 응답 또는 특정 URL 패턴)
                is_api_request = (
                    url.startswith('/admin/') or 
                    'application/json' in response.get('Content-Type', '') or
                    any(api_path in url for api_path in ['/api/', '/schedule/', '/chatbot/'])
                )
                
                request_data = {
                    'request_id': request_id,
                    'method': method,
                    'url': url,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'response_time': round(response_time, 2),
                    'status_code': response.status_code,
                    'response_size': len(response.content) if hasattr(response, 'content') else 0,
                }
                
                if is_api_request:
                    log_api_request(self.api_logger, request_data)
                else:
                    # 일반 HTTP 요청 로그
                    self.access_logger.info(
                        f"요청 완료: {method} {url} - {response.status_code} ({response_time:.2f}ms)",
                        extra=request_data
                    )
                
                # 성능 모니터링 (느린 요청 감지)
                if response_time > 2000:  # 2초 이상
                    self.access_logger.warning(
                        f"느린 요청 감지: {method} {url} - {response_time:.2f}ms",
                        extra=request_data
                    )
            
            return response
            
        except Exception as e:
            # 에러 로그 기록
            response_time = (time.time() - start_time) * 1000
            
            self.error_logger.error(
                f"요청 처리 중 에러: {method} {url} - {str(e)}",
                extra={
                    'request_id': request_id,
                    'method': method,
                    'url': url,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'response_time': round(response_time, 2),
                    'error_message': str(e),
                    'error_type': type(e).__name__,
                },
                exc_info=True
            )
            
            # 에러를 다시 발생시켜 정상적인 에러 처리 플로우 유지
            raise
    
    def get_client_ip(self, request):
        """클라이언트 IP 주소 추출"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip

class SecurityLoggingMiddleware:
    """보안 관련 이벤트 로깅 미들웨어"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.security_logger = create_logger('django_security', 'system', 'security')
        
        # 보안 이벤트 감지 패턴
        self.suspicious_patterns = [
            'script>',
            'javascript:',
            '../',
            'SELECT * FROM',
            'DROP TABLE',
            'UNION SELECT',
            'eval(',
            'base64',
        ]
        
        print("✅ Django 보안 로깃 미들웨어가 초기화되었습니다.")
    
    def __call__(self, request):
        # 보안 이벤트 체크
        self.check_security_events(request)
        
        response = self.get_response(request)
        return response
    
    def check_security_events(self, request):
        """보안 이벤트 감지 및 로깅"""
        request_id = getattr(_thread_local, 'request_id', 'unknown')
        ip_address = self.get_client_ip(request)
        url = request.get_full_path()
        
        # SQL Injection, XSS 등 의심스러운 패턴 체크
        query_string = request.META.get('QUERY_STRING', '')
        request_body = ''
        
        if hasattr(request, 'body'):
            try:
                request_body = request.body.decode('utf-8', errors='ignore')
            except:
                request_body = ''
        
        combined_data = f"{url} {query_string} {request_body}".lower()
        
        for pattern in self.suspicious_patterns:
            if pattern.lower() in combined_data:
                self.security_logger.warning(
                    f"의심스러운 요청 패턴 감지: {pattern}",
                    extra={
                        'request_id': request_id,
                        'ip_address': ip_address,
                        'url': url,
                        'method': request.method,
                        'pattern': pattern,
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'timestamp': timezone.now().isoformat(),
                    }
                )
                break
        
        # 비정상적으로 많은 요청 체크 (간단한 Rate Limiting 감지)
        # 실제 운영에서는 Redis 등을 사용한 더 정교한 구현이 필요
        if hasattr(request, 'session'):
            session_key = request.session.session_key
            if session_key:
                # 여기서는 간단히 로그만 남김 (실제 구현은 별도 필요)
                pass
    
    def get_client_ip(self, request):
        """클라이언트 IP 주소 추출"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip 