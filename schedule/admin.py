from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.shortcuts import render, get_object_or_404
from django.utils.html import format_html
from django import forms
from django.contrib import messages
from datetime import datetime
from .models import Department, Doctor, Schedule, WorkSchedule

class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'phone_number')
    list_filter = ('department',)
    search_fields = ('name', 'phone_number')

class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('date', 'weekday', 'doctor', 'work_schedule', 'is_on_call', 'note')
    list_filter = ('date', 'weekday', 'doctor__department', 'is_on_call')
    search_fields = ('doctor__name', 'note')
    date_hierarchy = 'date'
    
    def save_model(self, request, obj, form, change):
        # 요일 자동 계산
        weekday_map = {
            0: '월',
            1: '화',
            2: '수',
            3: '목',
            4: '금',
            5: '토',
            6: '일',
        }
        obj.weekday = weekday_map[obj.date.weekday()]
        super().save_model(request, obj, form, change)

class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'description')
    search_fields = ('start_time', 'end_time', 'description')

admin.site.register(Department, DepartmentAdmin)
admin.site.register(Doctor, DoctorAdmin)
admin.site.register(Schedule, ScheduleAdmin)
admin.site.register(WorkSchedule, WorkScheduleAdmin)
