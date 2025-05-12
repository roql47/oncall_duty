from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView, TemplateView, FormView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse_lazy
from datetime import datetime, timedelta
from .models import Department, Doctor, Schedule, WorkSchedule
from .forms import ScheduleForm, QuickScheduleForm, WorkScheduleForm
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
import calendar
from calendar import HTMLCalendar, monthrange
from datetime import date
from django.shortcuts import get_object_or_404

class HomeView(TemplateView):
    template_name = 'schedule/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        
        # 이번 달 일정 수
        current_month_schedules = Schedule.objects.filter(
            date__year=now.year,
            date__month=now.month
        ).count()
        
        # 전체 의사 수
        doctor_count = Doctor.objects.count()
        
        # 이번 달 당직 일정 수
        current_month_on_call = Schedule.objects.filter(
            date__year=now.year,
            date__month=now.month,
            is_on_call=True
        ).count()
        
        # 현재 날짜 기준 주차 계산
        first_day = datetime(now.year, now.month, 1).date()
        first_monday = first_day - timedelta(days=first_day.weekday())
        current_date = now.date()
        current_week = ((current_date - first_monday).days // 7) + 1
        
        context.update({
            'current_year': now.year,
            'current_month': now.month,
            'current_week': current_week,
            'current_month_schedules': current_month_schedules,
            'doctor_count': doctor_count,
            'current_month_on_call': current_month_on_call,
            'departments': Department.objects.all(),
            'user': self.request.user,
        })
        return context

class ScheduleMonthView(ListView):
    model = Schedule
    template_name = 'schedule/month_schedule.html'
    context_object_name = 'schedules'
    
    def get_queryset(self):
        year = int(self.kwargs.get('year', timezone.now().year))
        month = int(self.kwargs.get('month', timezone.now().month))
        
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        return Schedule.objects.filter(date__gte=start_date, date__lte=end_date)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = int(self.kwargs.get('year', timezone.now().year))
        month = int(self.kwargs.get('month', timezone.now().month))
        
        context['year'] = year
        context['month'] = month
        context['departments'] = Department.objects.all().order_by('name')
        context['user'] = self.request.user
        
        # 모든 의사 및 근무시간 (관리자용 드롭다운)
        if self.request.user.is_staff:
            context['all_doctors'] = Doctor.objects.all().order_by('name')
            context['all_work_schedules'] = WorkSchedule.objects.all().order_by('start_time')
        
        # 날짜별로 일정 그룹화 및 날짜 순서대로 정렬
        schedules_by_date = {}
        
        # 먼저 월의 모든 날짜 생성
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
            
        current_date = start_date
        while current_date <= end_date:
            schedules_by_date[current_date] = []
            current_date += timedelta(days=1)
        
        # 각 날짜에 해당하는 일정 할당 (일정을 근무시간, 의사이름 순으로 정렬)
        schedules = context['schedules'].select_related('doctor', 'doctor__department', 'work_schedule')
        
        for schedule in schedules:
            if schedule.date in schedules_by_date:
                schedules_by_date[schedule.date].append(schedule)
        
        # 정렬된 일정 딕셔너리로 변환
        from collections import OrderedDict
        schedules_by_date = OrderedDict(sorted(schedules_by_date.items()))
        
        # 각 날짜별 일정을 부서명 순으로 정렬
        for date, schedule_list in schedules_by_date.items():
            schedules_by_date[date] = sorted(schedule_list, key=lambda s: (s.doctor.department.name, s.work_schedule.start_time))
        
        context['schedules_by_date'] = schedules_by_date
        
        return context

class ScheduleWeekView(ListView):
    model = Schedule
    template_name = 'schedule/week_schedule.html'
    context_object_name = 'schedules'
    
    def get_queryset(self):
        year = int(self.kwargs.get('year', timezone.now().year))
        month = int(self.kwargs.get('month', timezone.now().month))
        week = int(self.kwargs.get('week', 1))
        
        # 해당 월의 첫날
        first_day = datetime(year, month, 1).date()
        
        # 해당 월의 첫날이 속한 주의 월요일
        first_monday = first_day - timedelta(days=first_day.weekday())
        
        # 주차에 따른 시작일 계산 (1주차는 해당 월의 첫날이 속한 주)
        start_date = first_monday + timedelta(weeks=week-1)
        end_date = start_date + timedelta(days=6)  # 주의 마지막 날 (일요일)
        
        return Schedule.objects.filter(date__gte=start_date, date__lte=end_date)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = int(self.kwargs.get('year', timezone.now().year))
        month = int(self.kwargs.get('month', timezone.now().month))
        week = int(self.kwargs.get('week', 1))
        
        # 해당 월의 첫날
        first_day = datetime(year, month, 1).date()
        
        # 해당 월의 첫날이 속한 주의 월요일
        first_monday = first_day - timedelta(days=first_day.weekday())
        
        # 주차에 따른 시작일과 종료일 계산
        start_date = first_monday + timedelta(weeks=week-1)
        end_date = start_date + timedelta(days=6)
        
        # 월의 마지막 날
        if month == 12:
            last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)
            
        # 마지막 주 계산
        last_week = ((last_day - first_monday).days // 7) + 1
        
        # 날짜별로 일정 그룹화
        schedules_by_date = {}
        
        # 일주일의 모든 날짜 생성
        current_date = start_date
        while current_date <= end_date:
            schedules_by_date[current_date] = []
            current_date += timedelta(days=1)
        
        # 각 날짜에 해당하는 일정 할당
        schedules = context['schedules'].select_related('doctor', 'doctor__department', 'work_schedule')
        
        for schedule in schedules:
            if schedule.date in schedules_by_date:
                schedules_by_date[schedule.date].append(schedule)
        
        # 정렬된 일정 딕셔너리로 변환
        from collections import OrderedDict
        schedules_by_date = OrderedDict(sorted(schedules_by_date.items()))
        
        # 각 날짜별 일정을 부서명 순으로 정렬
        for date, schedule_list in schedules_by_date.items():
            schedules_by_date[date] = sorted(schedule_list, key=lambda s: (s.doctor.department.name, s.work_schedule.start_time))
        
        context['schedules_by_date'] = schedules_by_date
        context['year'] = year
        context['month'] = month
        context['week'] = week
        context['start_date'] = start_date
        context['end_date'] = end_date
        context['last_week'] = last_week
        context['departments'] = Department.objects.all().order_by('name')
        context['weekday_names'] = ['월', '화', '수', '목', '금', '토', '일']
        context['user'] = self.request.user
        
        # 이전 주와 다음 주 계산
        prev_week = week - 1
        prev_month = month
        prev_year = year
        
        next_week = week + 1
        next_month = month
        next_year = year
        
        # 이전 주가 0이면 이전 달의 마지막 주로
        if prev_week < 1:
            prev_month = month - 1
            if prev_month < 1:
                prev_month = 12
                prev_year = year - 1
            
            # 이전 달의 마지막 날
            if prev_month == 12:
                prev_last_day = datetime(prev_year + 1, 1, 1).date() - timedelta(days=1)
            else:
                prev_last_day = datetime(prev_year, prev_month + 1, 1).date() - timedelta(days=1)
                
            # 이전 달의 첫 월요일
            prev_first_day = datetime(prev_year, prev_month, 1).date()
            prev_first_monday = prev_first_day - timedelta(days=prev_first_day.weekday())
            
            # 이전 달의 마지막 주
            prev_week = ((prev_last_day - prev_first_monday).days // 7) + 1
        
        # 다음 주가 마지막 주보다 크면 다음 달의 첫 주로
        if next_week > last_week:
            next_month = month + 1
            if next_month > 12:
                next_month = 1
                next_year = year + 1
            next_week = 1
        
        context['prev_year'] = prev_year
        context['prev_month'] = prev_month
        context['prev_week'] = prev_week
        context['next_year'] = next_year
        context['next_month'] = next_month
        context['next_week'] = next_week
        
        return context

class DepartmentScheduleView(ListView):
    model = Schedule
    template_name = 'schedule/department_schedule.html'
    context_object_name = 'schedules'
    
    def get_queryset(self):
        department_id = self.kwargs.get('department_id')
        year = int(self.kwargs.get('year', timezone.now().year))
        month = int(self.kwargs.get('month', timezone.now().month))
        
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        return Schedule.objects.filter(
            doctor__department_id=department_id,
            date__gte=start_date,
            date__lte=end_date
        ).select_related('doctor', 'work_schedule').order_by('date', 'work_schedule__start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department_id = self.kwargs.get('department_id')
        year = int(self.kwargs.get('year', timezone.now().year))
        month = int(self.kwargs.get('month', timezone.now().month))
        
        context['department'] = Department.objects.get(id=department_id)
        context['year'] = year
        context['month'] = month
        context['doctors'] = Doctor.objects.filter(department_id=department_id).order_by('name')
        
        # 날짜별로 일정 그룹화
        schedules_by_date = {}
        for schedule in context['schedules']:
            if schedule.date not in schedules_by_date:
                schedules_by_date[schedule.date] = []
            schedules_by_date[schedule.date].append(schedule)
        
        # 각 날짜별 스케줄을 시간순으로 정렬
        for date, schedule_list in schedules_by_date.items():
            schedules_by_date[date] = sorted(schedule_list, key=lambda s: s.work_schedule.start_time)
        
        # 정렬된 일정 딕셔너리로 변환 (날짜순)
        from collections import OrderedDict
        ordered_schedules = OrderedDict()
        for date in sorted(schedules_by_date.keys()):
            ordered_schedules[date] = schedules_by_date[date]
        
        context['schedules_by_date'] = ordered_schedules
        
        return context

class DoctorScheduleView(ListView):
    model = Schedule
    template_name = 'schedule/doctor_schedule.html'
    context_object_name = 'schedules'
    
    def get_queryset(self):
        doctor_id = self.kwargs.get('doctor_id')
        year = int(self.kwargs.get('year', timezone.now().year))
        month = int(self.kwargs.get('month', timezone.now().month))
        
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        return Schedule.objects.filter(
            doctor_id=doctor_id,
            date__gte=start_date,
            date__lte=end_date
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor_id = self.kwargs.get('doctor_id')
        year = int(self.kwargs.get('year', timezone.now().year))
        month = int(self.kwargs.get('month', timezone.now().month))
        
        context['doctor'] = Doctor.objects.get(id=doctor_id)
        context['year'] = year
        context['month'] = month
        
        return context

class ScheduleCreateView(FormView):
    template_name = 'schedule/schedule_form.html'
    form_class = ScheduleForm
    success_url = reverse_lazy('schedule:home')
    
    def form_valid(self, form):
        form.save()
        messages.success(self.request, '일정이 성공적으로 추가되었습니다.')
        return super().form_valid(form)

class QuickScheduleCreateView(FormView):
    template_name = 'schedule/quick_schedule_form.html'
    form_class = QuickScheduleForm
    success_url = reverse_lazy('schedule:home')
    
    def form_valid(self, form):
        schedule = form.save()
        messages.success(self.request, f"{schedule.doctor.name}의 일정이 성공적으로 추가되었습니다.")
        return super().form_valid(form)

class BatchScheduleUploadView(TemplateView):
    template_name = 'schedule/batch_upload.html'
    
    def post(self, request, *args, **kwargs):
        batch_text = request.POST.get('batch_text', '')
        results = self.process_batch_text(batch_text)
        
        context = self.get_context_data(**kwargs)
        context['results'] = results
        context['batch_text'] = batch_text
        return self.render_to_response(context)
    
    def process_batch_text(self, batch_text):
        lines = batch_text.strip().split('\n')
        results = []
        
        current_department = None
        current_phone = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 부서와 연락처 라인 처리
            if '연락처' in line or '전화번호' in line:
                parts = line.split('=')
                if len(parts) == 2:
                    dept_name = parts[0].strip()
                    phone = parts[1].strip()
                    
                    # 부서 찾기
                    try:
                        # 정확한 이름 매칭
                        current_department = Department.objects.filter(name__icontains=dept_name).first()
                        current_phone = phone
                        results.append({
                            'success': True,
                            'message': f"부서 설정: {current_department.name}, 연락처: {current_phone}"
                        })
                    except Exception as e:
                        results.append({
                            'success': False,
                            'message': f"부서를 찾을 수 없습니다: {dept_name}. 오류: {str(e)}"
                        })
            
            # 시간과 의사 정보 처리
            elif '시' in line and '~' in line:
                if not current_department or not current_phone:
                    results.append({
                        'success': False,
                        'message': f"부서와 연락처 정보가 필요합니다: {line}"
                    })
                    continue
                
                try:
                    # 시간 정보 추출
                    time_parts = line.split(' ', 1)
                    time_info = time_parts[0]
                    rest_info = time_parts[1] if len(time_parts) > 1 else ""
                    
                    # 시간 파싱
                    time_range = time_info.split('~')
                    
                    # 시간 형식 정규화
                    start_time_raw = time_range[0].replace('시', ':00')
                    end_time_raw = time_range[1].replace('시', ':00')
                    
                    # 24시간 형식으로 변환
                    def normalize_time(time_str):
                        if ':' not in time_str:
                            time_str += ':00'
                        
                        # 선택 가능한 시간 옵션에서 가장 가까운 값 찾기
                        for choice, _ in WorkSchedule.TIME_CHOICES:
                            if choice == time_str:
                                return choice
                        
                        # 매치되는 시간이 없으면 기본값 반환
                        return '08:00' if '08' in time_str else '17:00'
                    
                    start_time = normalize_time(start_time_raw)
                    end_time = normalize_time(end_time_raw)
                    
                    # 요일과 의사 정보 파싱
                    day_doctor_parts = rest_info.strip().split(' ', 1)
                    weekday = day_doctor_parts[0].strip()
                    doctor_name = day_doctor_parts[1].strip() if len(day_doctor_parts) > 1 else ""
                    
                    # 요일 매핑
                    weekday_map = {
                        '월요일': '월', '화요일': '화', '수요일': '수', '목요일': '목', 
                        '금요일': '금', '토요일': '토', '일요일': '일',
                        '월': '월', '화': '화', '수': '수', '목': '목', 
                        '금': '금', '토': '토', '일': '일'
                    }
                    
                    normalized_weekday = weekday_map.get(weekday, weekday)
                    
                    # 날짜 계산 (현재 주의 해당 요일)
                    today = timezone.now().date()
                    days_ahead = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}
                    days_ahead_normalized = days_ahead.get(normalized_weekday, 0)
                    
                    # 오늘의 요일 (0=월요일, 6=일요일)
                    today_weekday = today.weekday()
                    
                    # 다음 해당 요일까지의 일수 계산
                    days_until_target = (days_ahead_normalized - today_weekday) % 7
                    target_date = today + timedelta(days=days_until_target)
                    
                    # 의사 조회 또는 생성
                    doctor, created = Doctor.objects.get_or_create(
                        name=doctor_name,
                        department=current_department,
                        defaults={'phone_number': current_phone}
                    )
                    
                    # 근무 시간대 조회 또는 생성
                    work_schedule, _ = WorkSchedule.objects.get_or_create(
                        start_time=start_time,
                        end_time=end_time
                    )
                    
                    # 일정 생성
                    schedule = Schedule.objects.create(
                        date=target_date,
                        weekday=normalized_weekday,
                        doctor=doctor,
                        work_schedule=work_schedule,
                        is_on_call=False
                    )
                    
                    results.append({
                        'success': True,
                        'message': f"일정 추가: {doctor.name}, {schedule.date} ({normalized_weekday}), {start_time}~{end_time}"
                    })
                    
                except Exception as e:
                    results.append({
                        'success': False,
                        'message': f"일정 추가 실패: {line}. 오류: {str(e)}"
                    })
            
            else:
                results.append({
                    'success': False,
                    'message': f"인식할 수 없는 형식: {line}"
                })
        
        return results

class WorkScheduleListView(ListView):
    model = WorkSchedule
    template_name = 'schedule/work_schedule_list.html'
    context_object_name = 'work_schedules'
    ordering = ['start_time', 'end_time']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class WorkScheduleCreateView(CreateView):
    model = WorkSchedule
    form_class = WorkScheduleForm
    template_name = 'schedule/work_schedule_form.html'
    success_url = reverse_lazy('schedule:work_schedule_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '근무시간 추가'
        context['submit_text'] = '추가'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, '근무시간이 성공적으로 추가되었습니다.')
        return super().form_valid(form)

class WorkScheduleUpdateView(UpdateView):
    model = WorkSchedule
    form_class = WorkScheduleForm
    template_name = 'schedule/work_schedule_form.html'
    success_url = reverse_lazy('schedule:work_schedule_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '근무시간 수정'
        context['submit_text'] = '수정'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, '근무시간이 성공적으로 수정되었습니다.')
        return super().form_valid(form)

class WorkScheduleDeleteView(DeleteView):
    model = WorkSchedule
    template_name = 'schedule/work_schedule_confirm_delete.html'
    success_url = reverse_lazy('schedule:work_schedule_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, '근무시간이 성공적으로 삭제되었습니다.')
        return super().delete(request, *args, **kwargs)

def home(request):
    return render(request, 'schedule/home.html')

def get_date(req_day):
    if req_day:
        year, month = (int(x) for x in req_day.split('-'))
        return date(year, month, day=1)
    return datetime.today().date()

def prev_month(d):
    first = d.replace(day=1)
    prev_month = first - timedelta(days=1)
    return {'year': prev_month.year, 'month': prev_month.month}

def next_month(d):
    days_in_month = monthrange(d.year, d.month)[1]
    last = d.replace(day=days_in_month)
    next_month = last + timedelta(days=1)
    return {'year': next_month.year, 'month': next_month.month}

@login_required
def work_hours_calendar(request):
    """근무시간별 의사 배정 달력 뷰"""
    # 현재 보고 있는 날짜 가져오기 (기본값: 오늘)
    d = get_date(request.GET.get('month', None))
    
    # 달력 객체 생성
    cal = WorkCalendar(d.year, d.month)
    
    # HTML 달력 렌더링
    html_cal = cal.formatmonth(withyear=True)
    html_cal = mark_safe(html_cal)
    
    # 부서 및 근무시간 목록 가져오기
    departments = Department.objects.all()
    work_schedules = WorkSchedule.objects.all().order_by('start_time')
    doctors = Doctor.objects.all().order_by('name')
    
    context = {
        'html_cal': html_cal,
        'prev_month': prev_month(d),
        'next_month': next_month(d),
        'current_month': d,
        'departments': departments,
        'work_schedules': work_schedules,
        'doctors': doctors,
    }
    
    return render(request, 'schedule/work_hours_calendar.html', context)

@login_required
@require_POST
def assign_doctor(request):
    """AJAX 요청으로 의사 배정 처리"""
    try:
        date_str = request.POST.get('date')
        schedule_id = request.POST.get('work_schedule')
        doctor_id = request.POST.get('doctor')
        
        # 날짜 파싱
        year, month, day = map(int, date_str.split('-'))
        schedule_date = date(year, month, day)
        
        # 요일 계산
        weekday_map = {
            0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'
        }
        weekday = weekday_map[schedule_date.weekday()]
        
        # 근무시간 및 의사 객체 가져오기
        work_schedule = WorkSchedule.objects.get(id=schedule_id)
        doctor = Doctor.objects.get(id=doctor_id)
        
        # 이미 존재하는 일정 확인 및 업데이트/생성
        schedule, created = Schedule.objects.update_or_create(
            date=schedule_date,
            work_schedule=work_schedule,
            defaults={
                'weekday': weekday,
                'doctor': doctor,
                'is_on_call': False,  # 기본값, 필요시 수정 가능
            }
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f'{doctor.name}이(가) {schedule_date}에 배정되었습니다.',
            'doctor_name': doctor.name,
            'doctor_id': doctor.id
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'오류가 발생했습니다: {str(e)}'
        }, status=400)

class WorkCalendar(HTMLCalendar):
    """근무시간 배정을 위한 달력 클래스"""
    def __init__(self, year=None, month=None):
        self.year = year
        self.month = month
        super().__init__()
    
    def formatday(self, day, weekday):
        """날짜별 셀 형식 지정"""
        if day == 0:
            # 해당 월에 속하지 않는 날
            return '<td class="noday">&nbsp;</td>'
        
        # 현재 날짜 생성
        current_date = date(self.year, self.month, day)
        date_str = current_date.strftime('%Y-%m-%d')
        
        # 주말 스타일 클래스
        day_class = 'weekend' if weekday >= 5 else ''
        
        # 해당 날짜의 일정 조회
        schedules = Schedule.objects.filter(date=current_date).select_related('doctor', 'work_schedule')
        
        # 날짜 셀 HTML 시작
        html = f'<td class="{day_class} day-cell" data-date="{date_str}">'
        
        # 날짜 표시
        html += f'<div class="day-number">{day}</div>'
        
        # 근무시간별 의사 목록 표시 (placeholder)
        html += f'<div class="schedule-container" id="schedule-{date_str}">'
        
        # 기존 일정 표시
        if schedules.exists():
            for schedule in schedules:
                html += f'<div class="schedule-item" data-schedule-id="{schedule.id}" data-work-schedule="{schedule.work_schedule.id}">'
                html += f'<span class="time">{schedule.work_schedule}</span>: '
                html += f'<span class="doctor" data-doctor-id="{schedule.doctor.id}">{schedule.doctor.name}</span>'
                html += '</div>'
        
        html += '</div></td>'
        return html
    
    def formatweek(self, theweek):
        """주 형식 지정"""
        week = ''.join(self.formatday(d, wd) for (d, wd) in theweek)
        return f'<tr>{week}</tr>'
    
    def formatmonthname(self, theyear, themonth, withyear=True):
        """월 이름 형식 지정"""
        if withyear:
            s = f'{theyear}년 {themonth}월'
        else:
            s = f'{themonth}월'
        return f'<tr><th colspan="7" class="month-header">{s}</th></tr>'
    
    def formatmonth(self, withyear=True):
        """월 형식 지정"""
        cal = f'<table class="calendar">\n'
        cal += f'{self.formatmonthname(self.year, self.month, withyear=withyear)}\n'
        cal += f'{self.formatweekheader()}\n'
        
        for week in self.monthdays2calendar(self.year, self.month):
            cal += f'{self.formatweek(week)}\n'
        
        cal += '</table>'
        return cal

@login_required
def get_doctors_by_department(request):
    """부서별 의사 목록을 가져오는 AJAX 뷰"""
    department_id = request.GET.get('department_id')
    
    if not department_id:
        return JsonResponse({'error': '부서 ID가 필요합니다.'}, status=400)
    
    doctors = Doctor.objects.filter(department_id=department_id).order_by('name').values('id', 'name')
    
    return JsonResponse({
        'doctors': list(doctors)
    })

@login_required
def admin_schedule_edit(request, year=None, month=None):
    """관리자용 스케줄 편집 뷰"""
    if not request.user.is_staff:
        messages.error(request, '관리자만 접근할 수 있습니다.')
        return redirect('schedule:home')
    
    # 기본값으로 현재 연도와 월 사용
    if not year:
        year = datetime.today().year
    if not month:
        month = datetime.today().month
    
    # 부서 목록 가져오기
    departments = Department.objects.all().order_by('name')
    
    # 현재 월의 첫 날짜
    first_day = date(year, month, 1)
    
    # 월의 마지막 날짜
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    
    # 모든 근무 시간대 가져오기
    work_schedules = WorkSchedule.objects.all().order_by('start_time')
    
    # 이번 달의 모든 일정 가져오기
    schedules = Schedule.objects.filter(
        date__gte=first_day,
        date__lte=last_day
    ).select_related('doctor', 'doctor__department', 'work_schedule')
    
    # 요일명 배열
    weekday_names = ['월', '화', '수', '목', '금', '토', '일']
    
    # 날짜별 스케줄 데이터 생성
    schedule_data = {}
    current_date = first_day
    
    while current_date <= last_day:
        schedule_data[current_date] = {}
        
        # 근무시간별 의사 매핑
        for work_schedule in work_schedules:
            schedule_for_time = schedules.filter(
                date=current_date, 
                work_schedule=work_schedule
            ).first()
            
            if schedule_for_time:
                schedule_data[current_date][work_schedule.id] = {
                    'schedule_id': schedule_for_time.id,
                    'doctor_id': schedule_for_time.doctor.id,
                    'doctor_name': schedule_for_time.doctor.name,
                    'department': schedule_for_time.doctor.department.name,
                    'is_on_call': schedule_for_time.is_on_call
                }
    
        current_date += timedelta(days=1)
    
    # 날짜별 그룹을 요일별로 다시 그룹화
    calendar_weeks = []
    current_week = []
    
    # 첫 주의 시작 날짜 (월요일부터 시작하도록)
    first_weekday = first_day.weekday()  # 0=월요일, 6=일요일
    
    # 첫 주에 이전 달의 날짜 채우기
    if first_weekday > 0:
        for i in range(first_weekday):
            current_week.append(None)
    
    # 이번 달의 모든 날짜 추가
    current_date = first_day
    while current_date <= last_day:
        current_week.append(current_date)
        
        # 일요일이거나 마지막 날이면 주 완성
        if current_date.weekday() == 6 or current_date == last_day:
            # 마지막 주에 빈 날짜 채우기
            if current_date.weekday() < 6:
                for i in range(6 - current_date.weekday()):
                    current_week.append(None)
            
            calendar_weeks.append(current_week)
            current_week = []
        
        current_date += timedelta(days=1)
    
    # 모든 의사 가져오기
    doctors = Doctor.objects.all().order_by('name')
    
    # 다음 달과 이전 달 계산
    if month == 1:
        prev_month_year = year - 1
        prev_month_month = 12
    else:
        prev_month_year = year
        prev_month_month = month - 1
        
    if month == 12:
        next_month_year = year + 1
        next_month_month = 1
    else:
        next_month_year = year
        next_month_month = month + 1
    
    context = {
        'year': year,
        'month': month,
        'departments': departments,
        'work_schedules': work_schedules,
        'schedule_data': schedule_data,
        'calendar_weeks': calendar_weeks,
        'weekday_names': weekday_names,
        'doctors': doctors,
        'prev_month': {'year': prev_month_year, 'month': prev_month_month},
        'next_month': {'year': next_month_year, 'month': next_month_month},
    }
    
    return render(request, 'schedule/admin_schedule_edit.html', context)

@login_required
@require_POST
def update_schedule(request):
    """AJAX 요청으로 스케줄 업데이트 처리"""
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': '관리자만 접근할 수 있습니다.'}, status=403)
    
    try:
        date_str = request.POST.get('date')
        work_schedule_id = request.POST.get('work_schedule_id')
        doctor_id = request.POST.get('doctor_id')
        is_on_call = request.POST.get('is_on_call') == 'true'
        
        # 날짜 파싱
        year, month, day = map(int, date_str.split('-'))
        schedule_date = date(year, month, day)
        
        # 요일 계산
        weekday_map = {
            0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'
        }
        weekday = weekday_map[schedule_date.weekday()]
        
        # 근무시간 및 의사 객체 가져오기
        work_schedule = WorkSchedule.objects.get(id=work_schedule_id)
        doctor = Doctor.objects.get(id=doctor_id)
        
        # 이미 존재하는 일정 확인 및 업데이트/생성
        schedule, created = Schedule.objects.update_or_create(
            date=schedule_date,
            work_schedule=work_schedule,
            defaults={
                'weekday': weekday,
                'doctor': doctor,
                'is_on_call': is_on_call,
            }
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f'{doctor.name}이(가) {schedule_date}에 배정되었습니다.',
            'doctor': {
                'id': doctor.id,
                'name': doctor.name,
                'department': doctor.department.name
            },
            'is_on_call': is_on_call
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'오류가 발생했습니다: {str(e)}'
        }, status=400)

@login_required
@require_POST
def update_month_schedule(request):
    """AJAX 요청을 처리하여 월간 스케줄을 업데이트합니다."""
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            date_str = request.POST.get('date')
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            work_schedule_id = request.POST.get('work_schedule_id')
            doctor_id = request.POST.get('doctor_id')
            is_on_call = request.POST.get('is_on_call') == 'true'
            
            work_schedule = get_object_or_404(WorkSchedule, id=work_schedule_id)
            doctor = get_object_or_404(Doctor, id=doctor_id)
            department_id = doctor.department.id
            
            # 근무 시간대가 해당 부서에 할당되어 있는지 확인
            if work_schedule.departments.filter(id=department_id).exists() or not work_schedule.departments.exists():
                # 같은 날짜, 같은 근무시간, 같은 부서에 이미 존재하는 스케줄 확인
                existing_schedule = Schedule.objects.filter(
                    date=date_obj,
                    work_schedule=work_schedule,
                    doctor__department=doctor.department
                ).first()
                
                weekday = ['월', '화', '수', '목', '금', '토', '일'][date_obj.weekday()]
                
                if existing_schedule:
                    # 기존 일정 업데이트
                    existing_schedule.doctor = doctor
                    existing_schedule.is_on_call = is_on_call
                    existing_schedule.weekday = weekday
                    existing_schedule.save()
                    schedule = existing_schedule
                else:
                    # 새 일정 생성
                    schedule = Schedule.objects.create(
                        date=date_obj,
                        work_schedule=work_schedule,
                        doctor=doctor,
                        is_on_call=is_on_call,
                        weekday=weekday
                    )
                
                return JsonResponse({
                    'status': 'success',
                    'schedule_id': schedule.id,
                    'doctor': {
                        'name': doctor.name,
                        'phone_number': doctor.phone_number or ''
                    }
                })
            else:
                return JsonResponse({
                    'status': 'error', 
                    'message': f'해당 근무 시간대({work_schedule})는 {doctor.department.name} 부서에서 사용할 수 없습니다.'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청입니다.'}, status=400)

def delete_schedule(request):
    """AJAX 요청을 처리하여 스케줄을 삭제합니다."""
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            schedule_id = request.POST.get('schedule_id')
            schedule = get_object_or_404(Schedule, id=schedule_id)
            schedule.delete()
            
            return JsonResponse({
                'status': 'success',
                'message': '스케줄이 삭제되었습니다.'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청입니다.'}, status=400)

@login_required
def get_work_schedules(request):
    """근무시간 목록을 JSON으로 반환하는 AJAX 뷰"""
    department_id = request.GET.get('department_id')
    
    if department_id:
        # 특정 부서 ID가 제공된 경우, 해당 부서에 연결된 근무 시간대만 반환
        department = get_object_or_404(Department, id=department_id)
        work_schedules = department.work_schedules.all().order_by('start_time')
        
        # 부서에 연결된 근무 시간대가 없으면 모든 근무 시간대 반환
        if not work_schedules.exists():
            work_schedules = WorkSchedule.objects.all().order_by('start_time')
    else:
        # 부서 ID가 제공되지 않은 경우 모든 근무 시간대 반환
        work_schedules = WorkSchedule.objects.all().order_by('start_time')
    
    data = {
        'work_schedules': [
            {
                'id': ws.id,
                'display': str(ws)
            } for ws in work_schedules
        ]
    }
    return JsonResponse(data)

@login_required
def get_work_schedules_by_department(request):
    """특정 부서에 할당된 근무시간 목록만 JSON으로 반환하는 AJAX 뷰"""
    department_id = request.GET.get('department_id')
    
    if not department_id:
        return JsonResponse({'status': 'error', 'message': '부서 ID가 필요합니다.'}, status=400)
    
    try:
        department = get_object_or_404(Department, id=department_id)
        
        # 해당 부서에 명시적으로 할당된 근무 시간대 가져오기
        department_work_schedules = WorkSchedule.objects.filter(departments=department).order_by('start_time')
        
        # 특정 부서에 할당되지 않은 모든 부서 공통 근무 시간대 가져오기
        common_work_schedules = WorkSchedule.objects.filter(departments__isnull=True).order_by('start_time')
        
        # 두 쿼리셋 병합
        work_schedules = list(department_work_schedules) + list(common_work_schedules)
        
        data = {
            'status': 'success',
            'work_schedules': [
                {
                    'id': ws.id,
                    'display': str(ws)
                } for ws in work_schedules
            ]
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
