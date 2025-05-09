from django.utils import timezone

class CurrentDateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        now = timezone.now()
        request.current_year = now.year
        request.current_month = now.month
        request.current_day = now.day
        
        response = self.get_response(request)
        return response 