from django.db import models
from django.contrib.auth.models import User


class Student(models.Model):
    """Model lưu thông tin sinh viên"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    student_id = models.CharField(max_length=20, unique=True, verbose_name="Student ID")
    full_name = models.CharField(max_length=100, verbose_name="Full name")
    email = models.EmailField(blank=True, verbose_name="Email")
    class_name = models.CharField(max_length=50, blank=True, verbose_name="Class")
    face_encoding = models.BinaryField(null=True, blank=True, verbose_name="Face encoding data")
    face_image = models.ImageField(upload_to='faces/', null=True, blank=True, verbose_name="Face image")
    is_registered = models.BooleanField(default=False, verbose_name="Face registered")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"
        ordering = ['student_id']

    def __str__(self):
        return f"{self.student_id} - {self.full_name}"


class Subject(models.Model):
    """Model lưu thông tin môn học"""
    code = models.CharField(max_length=20, unique=True, verbose_name="Subject code")
    name = models.CharField(max_length=100, verbose_name="Subject name")
    teacher = models.CharField(max_length=100, blank=True, verbose_name="Teacher")
    credits = models.IntegerField(default=3, verbose_name="Credits")
    
    class Meta:
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class ClassRoom(models.Model):
    """Model lưu thông tin lớp học"""
    class_id = models.CharField(max_length=20, unique=True, verbose_name="Class ID")
    name = models.CharField(max_length=100, verbose_name="Class name")
    department = models.CharField(max_length=100, blank=True, verbose_name="Department")
    students = models.ManyToManyField(Student, related_name='classrooms', blank=True, verbose_name="Students")
    
    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"
    
    def __str__(self):
        return f"{self.class_id} - {self.name}"


class Schedule(models.Model):
    """Model lưu thời khóa biểu - Buổi học"""
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    PERIOD_CHOICES = [
        (1, 'Period 1 (7:00 - 7:50)'),
        (2, 'Period 2 (7:50 - 8:40)'),
        (3, 'Period 3 (8:50 - 9:40)'),
        (4, 'Period 4 (9:40 - 10:30)'),
        (5, 'Period 5 (10:40 - 11:30)'),
        (6, 'Period 6 (13:00 - 13:50)'),
        (7, 'Period 7 (13:50 - 14:40)'),
        (8, 'Period 8 (14:50 - 15:40)'),
        (9, 'Period 9 (15:40 - 16:30)'),
        (10, 'Period 10 (16:40 - 17:30)'),
    ]
    
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Subject")
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, verbose_name="Class")
    day_of_week = models.IntegerField(choices=DAY_CHOICES, verbose_name="Day")
    start_period = models.IntegerField(choices=PERIOD_CHOICES, verbose_name="Start period")
    end_period = models.IntegerField(choices=PERIOD_CHOICES, verbose_name="End period")
    room = models.CharField(max_length=50, blank=True, verbose_name="Room")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    
    class Meta:
        verbose_name = "Schedule"
        verbose_name_plural = "Schedules"
        ordering = ['day_of_week', 'start_period']
    
    def __str__(self):
        return f"{self.subject.name} - {self.classroom.name} - {self.get_day_of_week_display()}"
    
    def get_time_range(self):
        """Trả về khoảng thời gian của buổi học"""
        period_times = {
            1: ('7:00', '7:50'),
            2: ('7:50', '8:40'),
            3: ('8:50', '9:40'),
            4: ('9:40', '10:30'),
            5: ('10:40', '11:30'),
            6: ('13:00', '13:50'),
            7: ('13:50', '14:40'),
            8: ('14:50', '15:40'),
            9: ('15:40', '16:30'),
            10: ('16:40', '17:30'),
        }
        start = period_times.get(self.start_period, ('', ''))[0]
        end = period_times.get(self.end_period, ('', ''))[1]
        return f"{start} - {end}"


class AttendanceSession(models.Model):
    """Model lưu buổi điểm danh - Mỗi buổi học cụ thể có 1 ID riêng"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('postponed', 'Postponed'),
    ]
    
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, verbose_name="Schedule")
    external_session_id = models.CharField(max_length=80, unique=True, null=True, blank=True, verbose_name="External session ID")
    date = models.DateField(verbose_name="Class date")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', verbose_name="Status")
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="Attendance start time")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="Attendance end time")
    notes = models.TextField(blank=True, verbose_name="Notes")
    postponed_to = models.DateField(null=True, blank=True, verbose_name="Postponed to")
    postponed_reason = models.CharField(max_length=240, blank=True, verbose_name="Postponement reason")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Attendance session"
        verbose_name_plural = "Attendance sessions"
        ordering = ['-date', '-created_at']
        unique_together = ['schedule', 'date']
    
    def __str__(self):
        return f"#{self.id} - {self.schedule.subject.name} - {self.schedule.classroom.name} - {self.date}"
    
    def get_present_count(self):
        return self.session_records.filter(status='present').count()
    
    def get_total_students(self):
        return self.schedule.classroom.students.count()


class AttendanceRecord(models.Model):
    """Model lưu lịch sử điểm danh - Liên kết với buổi điểm danh"""
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('late', 'Late'),
        ('absent', 'Absent'),
    ]

    attendance_id = models.CharField(max_length=40, unique=True, null=True, blank=True, verbose_name="Attendance ID")
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='session_records', null=True, blank=True, verbose_name="Attendance session")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(verbose_name="Date")
    time_in = models.TimeField(null=True, blank=True, verbose_name="Check-in time")
    time_out = models.TimeField(null=True, blank=True, verbose_name="Check-out time")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present', verbose_name="Status")
    confidence = models.FloatField(default=0.0, verbose_name="Recognition confidence (%)")
    camera_id = models.CharField(max_length=50, blank=True, verbose_name="Camera ID")
    scheduled_time = models.TimeField(null=True, blank=True, verbose_name="Scheduled time")
    late_minutes = models.PositiveIntegerField(default=0, verbose_name="Late minutes")
    attendance_code = models.CharField(max_length=40, blank=True, verbose_name="Status code")
    attendance_label = models.CharField(max_length=80, blank=True, verbose_name="Status label")
    attendance_periods = models.PositiveIntegerField(null=True, blank=True, verbose_name="Counted periods")
    method = models.CharField(max_length=40, default='FACIAL_RECOGNITION', verbose_name="Method")
    device_id = models.CharField(max_length=80, blank=True, verbose_name="Device")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Attendance record"
        verbose_name_plural = "Attendance records"
        ordering = ['-date', '-time_in']
        constraints = [
            models.UniqueConstraint(fields=['session', 'student'], name='uniq_attendance_session_student'),
        ]

    def __str__(self):
        session_info = f" - Session #{self.session.id}" if self.session else ""
        return f"{self.student.full_name} - {self.date}{session_info} - {self.get_status_display()}"


class Grade(models.Model):
    """Điểm thành phần của sinh viên theo học phần và học kỳ."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='grades')
    semester = models.CharField(max_length=30, default='', blank=True)
    assessment_type = models.CharField(max_length=40, default='TOTAL')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['subject__code', 'assessment_type']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'subject', 'semester', 'assessment_type'],
                name='uniq_grade_student_subject_semester_type',
            ),
        ]

    def __str__(self):
        return f"{self.student.student_id} - {self.subject.code} - {self.assessment_type}: {self.score}"


class Camera(models.Model):
    """Model quản lý camera"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Maintenance'),
    ]

    camera_id = models.CharField(max_length=50, unique=True, verbose_name="Camera ID")
    name = models.CharField(max_length=100, verbose_name="Camera name")
    location = models.CharField(max_length=200, verbose_name="Location")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP address")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Status")
    last_active = models.DateTimeField(null=True, blank=True, verbose_name="Last active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Camera"
        verbose_name_plural = "Cameras"

    def __str__(self):
        return f"{self.name} ({self.camera_id})"


class SystemStats(models.Model):
    """Model lưu thống kê hệ thống"""
    date = models.DateField(unique=True, verbose_name="Date")
    total_students = models.IntegerField(default=0, verbose_name="Total students")
    attendance_rate = models.FloatField(default=0.0, verbose_name="Attendance rate (%)")
    avg_scan_time = models.FloatField(default=0.0, verbose_name="Average scan time (s)")
    total_scans = models.IntegerField(default=0, verbose_name="Total scans")

    class Meta:
        verbose_name = "System statistics"
        verbose_name_plural = "System statistics"
        ordering = ['-date']

    def __str__(self):
        return f"Stats - {self.date}"
