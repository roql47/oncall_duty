from django.db import models

# Create your models here.

class Department(models.Model):
    DEPARTMENT_CHOICES = [
        ('순환기내과', '순환기내과'),
        ('순환기내과 병동', '순환기내과 병동'),
        ('분과통합(순환기내과 제외)', '분과통합(순환기내과 제외)'),
        ('내과계 중환자실', '내과계 중환자실'),
        ('소화기내과 응급내시경(on call)', '소화기내과 응급내시경(on call)'),
        ('외과(ER call only)', '외과(ER call only)'),
        ('외과 당직의', '외과 당직의'),
        ('외과 수술의', '외과 수술의'),
        ('외과계 중환자실', '외과계 중환자실'),
        ('산부인과', '산부인과'),
        ('소아과 ER', '소아과 ER'),
        ('소아과 병동', '소아과 병동'),
        ('소아과 NICU', '소아과 NICU'),
        ('신경과', '신경과'),
        ('신경외과', '신경외과'),
        ('정형외과', '정형외과'),
        ('재활의학과', '재활의학과'),
        ('성형외과', '성형외과'),
        ('폐식도외과', '폐식도외과'),
        ('심장혈관외과', '심장혈관외과'),
        ('비뇨의학과', '비뇨의학과'),
        ('이비인후과(on call)', '이비인후과(on call)'),
        ('마취통증의학과', '마취통증의학과'),
        ('응급의학과', '응급의학과'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='부서명', choices=DEPARTMENT_CHOICES)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = '부서'
        verbose_name_plural = '부서'

class WorkSchedule(models.Model):
    """근무 시간대 설정 모델"""
    TIME_CHOICES = [
        ('00:00', '00:00'), ('00:30', '00:30'),
        ('01:00', '01:00'), ('01:30', '01:30'),
        ('02:00', '02:00'), ('02:30', '02:30'),
        ('03:00', '03:00'), ('03:30', '03:30'),
        ('04:00', '04:00'), ('04:30', '04:30'),
        ('05:00', '05:00'), ('05:30', '05:30'),
        ('06:00', '06:00'), ('06:30', '06:30'),
        ('07:00', '07:00'), ('07:30', '07:30'),
        ('08:00', '08:00'), ('08:30', '08:30'),
        ('09:00', '09:00'), ('09:30', '09:30'),
        ('10:00', '10:00'), ('10:30', '10:30'),
        ('11:00', '11:00'), ('11:30', '11:30'),
        ('12:00', '12:00'), ('12:30', '12:30'),
        ('13:00', '13:00'), ('13:30', '13:30'),
        ('14:00', '14:00'), ('14:30', '14:30'),
        ('15:00', '15:00'), ('15:30', '15:30'),
        ('16:00', '16:00'), ('16:30', '16:30'),
        ('17:00', '17:00'), ('17:30', '17:30'),
        ('18:00', '18:00'), ('18:30', '18:30'),
        ('19:00', '19:00'), ('19:30', '19:30'),
        ('20:00', '20:00'), ('20:30', '20:30'),
        ('21:00', '21:00'), ('21:30', '21:30'),
        ('22:00', '22:00'), ('22:30', '22:30'),
        ('23:00', '23:00'), ('23:30', '23:30'),
    ]
    
    start_time = models.CharField(max_length=10, verbose_name='시작 시간', choices=TIME_CHOICES)
    end_time = models.CharField(max_length=10, verbose_name='종료 시간', choices=TIME_CHOICES)
    description = models.CharField(max_length=100, blank=True, null=True, verbose_name='설명')
    
    def __str__(self):
        if self.description:
            return f"{self.start_time} - {self.end_time} ({self.description})"
        return f"{self.start_time} - {self.end_time}"
    
    class Meta:
        verbose_name = '근무 시간대'
        verbose_name_plural = '근무 시간대'
        ordering = ['start_time', 'end_time']
        unique_together = ['start_time', 'end_time', 'description']

class Doctor(models.Model):
    name = models.CharField(max_length=100, verbose_name='이름')
    phone_number = models.CharField(max_length=15, verbose_name='연락처')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='doctors', verbose_name='부서')
    
    def __str__(self):
        return f"{self.name} ({self.department})"
    
    class Meta:
        verbose_name = '의사'
        verbose_name_plural = '의사'

class Schedule(models.Model):
    WEEKDAY_CHOICES = [
        ('월', '월'),
        ('화', '화'),
        ('수', '수'),
        ('목', '목'),
        ('금', '금'),
        ('토', '토'),
        ('일', '일'),
    ]
    
    date = models.DateField(verbose_name='날짜')
    weekday = models.CharField(max_length=10, choices=WEEKDAY_CHOICES, verbose_name='요일')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='schedules', verbose_name='의사')
    work_schedule = models.ForeignKey(WorkSchedule, on_delete=models.CASCADE, related_name='schedules', verbose_name='근무시간', null=True)
    is_on_call = models.BooleanField(default=False, verbose_name='당직 여부')
    note = models.TextField(blank=True, null=True, verbose_name='비고')
    
    def __str__(self):
        return f"{self.date} {self.weekday} - {self.doctor.name} ({self.work_schedule})"
    
    class Meta:
        verbose_name = '일정'
        verbose_name_plural = '일정'
        ordering = ['date', 'work_schedule__start_time']
