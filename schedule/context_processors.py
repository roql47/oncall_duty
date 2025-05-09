def current_date_processor(request):
    """
    현재 연도와 달을 템플릿에 제공합니다.
    """
    return {
        'current_year': getattr(request, 'current_year', None),
        'current_month': getattr(request, 'current_month', None),
        'current_day': getattr(request, 'current_day', None),
    } 