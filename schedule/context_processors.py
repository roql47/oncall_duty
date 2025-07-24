from django.utils import timezone
import calendar

def current_date_processor(request):
    """
    현재 연도와 달을 템플릿에 제공합니다.
    """
    now = timezone.now()
    
    # 현재 주차 계산
    current_week = (now.day - 1) // 7 + 1
    
    return {
        'current_year': now.year,
        'current_month': now.month,
        'current_day': now.day,
        'current_week': current_week,
    } 