from django import forms
from .models import Department, Doctor, WorkSchedule, Schedule
from django.utils import timezone
import datetime

class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ['date', 'weekday', 'doctor', 'work_schedule', 'is_on_call', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

class WorkScheduleForm(forms.ModelForm):
    class Meta:
        model = WorkSchedule
        fields = ['start_time', 'end_time', 'description']
        widgets = {
            'start_time': forms.Select(attrs={'class': 'form-select'}),
            'end_time': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }

class QuickScheduleForm(forms.Form):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        label='부서',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    phone_number = forms.CharField(
        max_length=15, 
        label='연락처',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    date = forms.DateField(
        label='날짜',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=timezone.now().date
    )
    
    weekday = forms.ChoiceField(
        choices=Schedule.WEEKDAY_CHOICES,
        label='요일',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    start_time = forms.ChoiceField(
        choices=WorkSchedule.TIME_CHOICES,
        label='시작 시간',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    end_time = forms.ChoiceField(
        choices=WorkSchedule.TIME_CHOICES,
        label='종료 시간',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    doctor_name = forms.CharField(
        max_length=100,
        label='의사 이름',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    is_on_call = forms.BooleanField(
        required=False,
        label='당직 여부',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    note = forms.CharField(
        required=False,
        label='비고',
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # 요일 자동 계산
        if cleaned_data.get('date'):
            weekday_map = {
                0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'
            }
            date_obj = cleaned_data.get('date')
            weekday_num = date_obj.weekday()
            cleaned_data['weekday'] = weekday_map[weekday_num]
        
        # 시작 시간이 종료 시간보다 늦은 경우 검증
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time:
            if start_time >= end_time:
                raise forms.ValidationError('시작 시간은 종료 시간보다 빨라야 합니다.')
        
        return cleaned_data
    
    def save(self):
        department = self.cleaned_data['department']
        phone_number = self.cleaned_data['phone_number']
        date = self.cleaned_data['date']
        weekday = self.cleaned_data['weekday']
        start_time = self.cleaned_data['start_time']
        end_time = self.cleaned_data['end_time']
        doctor_name = self.cleaned_data['doctor_name']
        is_on_call = self.cleaned_data['is_on_call']
        note = self.cleaned_data['note']
        
        # 의사 조회 또는 생성
        doctor, created = Doctor.objects.get_or_create(
            name=doctor_name,
            department=department,
            defaults={'phone_number': phone_number}
        )
        
        # 이미 있는 의사라면 연락처 업데이트
        if not created and doctor.phone_number != phone_number:
            doctor.phone_number = phone_number
            doctor.save()
        
        # 근무 시간대 조회 또는 생성
        work_schedule, _ = WorkSchedule.objects.get_or_create(
            start_time=start_time,
            end_time=end_time
        )
        
        # 일정 생성
        schedule = Schedule.objects.create(
            date=date,
            weekday=weekday,
            doctor=doctor,
            work_schedule=work_schedule,
            is_on_call=is_on_call,
            note=note
        )
        
        return schedule 