from django.db import models
from django.contrib.auth.models import User


class Student(models.Model):
    """Model lưu thông tin sinh viên"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    student_id = models.CharField(max_length=20, unique=True, verbose_name="Mã sinh viên")
    full_name = models.CharField(max_length=100, verbose_name="Họ và tên")
    email = models.EmailField(blank=True, verbose_name="Email")
    class_name = models.CharField(max_length=50, blank=True, verbose_name="Lớp")
    face_encoding = models.BinaryField(null=True, blank=True, verbose_name="Face Encoding Data")
    face_image = models.ImageField(upload_to='faces/', null=True, blank=True, verbose_name="Ảnh khuôn mặt")
    is_registered = models.BooleanField(default=False, verbose_name="Đã đăng ký khuôn mặt")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sinh viên"
        verbose_name_plural = "Danh sách sinh viên"
        ordering = ['student_id']

    def __str__(self):
        return f"{self.student_id} - {self.full_name}"


class Subject(models.Model):
    """Model lưu thông tin môn học"""
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã môn học")
    name = models.CharField(max_length=100, verbose_name="Tên môn học")
    teacher = models.CharField(max_length=100, blank=True, verbose_name="Giảng viên")
    credits = models.IntegerField(default=3, verbose_name="Số tín chỉ")
    
    class Meta:
        verbose_name = "Môn học"
        verbose_name_plural = "Danh sách môn học"
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class ClassRoom(models.Model):
    """Model lưu thông tin lớp học"""
    class_id = models.CharField(max_length=20, unique=True, verbose_name="Mã lớp")
    name = models.CharField(max_length=100, verbose_name="Tên lớp")
    department = models.CharField(max_length=100, blank=True, verbose_name="Khoa")
    students = models.ManyToManyField(Student, related_name='classrooms', blank=True, verbose_name="Danh sách sinh viên")
    
    class Meta:
        verbose_name = "Lớp học"
        verbose_name_plural = "Danh sách lớp học"
    
    def __str__(self):
        return f"{self.class_id} - {self.name}"


class Schedule(models.Model):
    """Model lưu thời khóa biểu - Buổi học"""
    DAY_CHOICES = [
        (0, 'Thứ Hai'),
        (1, 'Thứ Ba'),
        (2, 'Thứ Tư'),
        (3, 'Thứ Năm'),
        (4, 'Thứ Sáu'),
        (5, 'Thứ Bảy'),
        (6, 'Chủ Nhật'),
    ]
    
    PERIOD_CHOICES = [
        (1, 'Tiết 1 (7:00 - 7:50)'),
        (2, 'Tiết 2 (7:50 - 8:40)'),
        (3, 'Tiết 3 (8:50 - 9:40)'),
        (4, 'Tiết 4 (9:40 - 10:30)'),
        (5, 'Tiết 5 (10:40 - 11:30)'),
        (6, 'Tiết 6 (13:00 - 13:50)'),
        (7, 'Tiết 7 (13:50 - 14:40)'),
        (8, 'Tiết 8 (14:50 - 15:40)'),
        (9, 'Tiết 9 (15:40 - 16:30)'),
        (10, 'Tiết 10 (16:40 - 17:30)'),
    ]
    
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Môn học")
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, verbose_name="Lớp học")
    day_of_week = models.IntegerField(choices=DAY_CHOICES, verbose_name="Thứ")
    start_period = models.IntegerField(choices=PERIOD_CHOICES, verbose_name="Tiết bắt đầu")
    end_period = models.IntegerField(choices=PERIOD_CHOICES, verbose_name="Tiết kết thúc")
    room = models.CharField(max_length=50, blank=True, verbose_name="Phòng học")
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")
    
    class Meta:
        verbose_name = "Thời khóa biểu"
        verbose_name_plural = "Thời khóa biểu"
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
        ('scheduled', 'Đã lên lịch'),
        ('active', 'Đang điểm danh'),
        ('completed', 'Đã kết thúc'),
        ('cancelled', 'Đã hủy'),
    ]
    
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, verbose_name="Thời khóa biểu")
    date = models.DateField(verbose_name="Ngày học")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', verbose_name="Trạng thái")
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian bắt đầu điểm danh")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian kết thúc điểm danh")
    notes = models.TextField(blank=True, verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Buổi điểm danh"
        verbose_name_plural = "Các buổi điểm danh"
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
        ('present', 'Có mặt'),
        ('late', 'Đi muộn'),
        ('absent', 'Vắng mặt'),
    ]

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='session_records', null=True, blank=True, verbose_name="Buổi điểm danh")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(verbose_name="Ngày")
    time_in = models.TimeField(null=True, blank=True, verbose_name="Giờ quét mặt")
    time_out = models.TimeField(null=True, blank=True, verbose_name="Giờ ra")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present', verbose_name="Trạng thái")
    confidence = models.FloatField(default=0.0, verbose_name="Độ tin cậy nhận diện (%)")
    camera_id = models.CharField(max_length=50, blank=True, verbose_name="ID Camera")
    notes = models.TextField(blank=True, verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bản ghi điểm danh"
        verbose_name_plural = "Lịch sử điểm danh"
        ordering = ['-date', '-time_in']

    def __str__(self):
        session_info = f" - Buổi #{self.session.id}" if self.session else ""
        return f"{self.student.full_name} - {self.date}{session_info} - {self.get_status_display()}"


class Camera(models.Model):
    """Model quản lý camera"""
    STATUS_CHOICES = [
        ('active', 'Hoạt động'),
        ('inactive', 'Không hoạt động'),
        ('maintenance', 'Bảo trì'),
    ]

    camera_id = models.CharField(max_length=50, unique=True, verbose_name="ID Camera")
    name = models.CharField(max_length=100, verbose_name="Tên camera")
    location = models.CharField(max_length=200, verbose_name="Vị trí")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Địa chỉ IP")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Trạng thái")
    last_active = models.DateTimeField(null=True, blank=True, verbose_name="Hoạt động lần cuối")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Camera"
        verbose_name_plural = "Danh sách camera"

    def __str__(self):
        return f"{self.name} ({self.camera_id})"


class SystemStats(models.Model):
    """Model lưu thống kê hệ thống"""
    date = models.DateField(unique=True, verbose_name="Ngày")
    total_students = models.IntegerField(default=0, verbose_name="Tổng số sinh viên")
    attendance_rate = models.FloatField(default=0.0, verbose_name="Tỷ lệ điểm danh (%)")
    avg_scan_time = models.FloatField(default=0.0, verbose_name="Thời gian scan trung bình (s)")
    total_scans = models.IntegerField(default=0, verbose_name="Tổng số lần scan")

    class Meta:
        verbose_name = "Thống kê hệ thống"
        verbose_name_plural = "Thống kê hệ thống"
        ordering = ['-date']

    def __str__(self):
        return f"Stats - {self.date}"
