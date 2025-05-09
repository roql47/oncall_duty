from django.urls import path
from . import views

app_name = 'schedule'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('schedule/<int:year>/<int:month>/', views.ScheduleMonthView.as_view(), name='month_schedule'),
    path('schedule/<int:year>/<int:month>/week/<int:week>/', views.ScheduleWeekView.as_view(), name='week_schedule'),
    path('department/<int:department_id>/<int:year>/<int:month>/', views.DepartmentScheduleView.as_view(), name='department_schedule'),
    path('doctor/<int:doctor_id>/<int:year>/<int:month>/', views.DoctorScheduleView.as_view(), name='doctor_schedule'),
    path('schedule/add/', views.ScheduleCreateView.as_view(), name='add_schedule'),
    path('schedule/quick-add/', views.QuickScheduleCreateView.as_view(), name='quick_add_schedule'),
    path('schedule/batch-upload/', views.BatchScheduleUploadView.as_view(), name='batch_upload'),
    path('work-schedules/', views.WorkScheduleListView.as_view(), name='work_schedule_list'),
    path('work-schedules/add/', views.WorkScheduleCreateView.as_view(), name='add_work_schedule'),
    path('work-schedules/<int:pk>/edit/', views.WorkScheduleUpdateView.as_view(), name='edit_work_schedule'),
    path('work-schedules/<int:pk>/delete/', views.WorkScheduleDeleteView.as_view(), name='delete_work_schedule'),
    
    # 근무시간 관리 URL
    path('work-hours-calendar/', views.work_hours_calendar, name='work_hours_calendar'),
    path('assign_doctor/', views.assign_doctor, name='assign_doctor'),
    path('ajax/get_doctors_by_department/', views.get_doctors_by_department, name='get_doctors_by_department'),
    path('ajax/get_work_schedules/', views.get_work_schedules, name='get_work_schedules'),
    
    # 관리자용 스케줄 편집 URL
    path('admin/schedule/', views.admin_schedule_edit, name='admin_schedule_edit'),
    path('admin/schedule/<int:year>/<int:month>/', views.admin_schedule_edit, name='admin_schedule_edit_date'),
    path('admin/update_schedule/', views.update_schedule, name='update_schedule'),
    path('update_month_schedule/', views.update_month_schedule, name='update_month_schedule'),
    path('delete_schedule/', views.delete_schedule, name='delete_schedule'),
] 