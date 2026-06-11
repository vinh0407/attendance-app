from django.contrib import admin
from .models import Student, AttendanceRecord, Camera, SystemStats, Subject, ClassRoom, Schedule, AttendanceSession


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'full_name', 'class_name', 'is_registered', 'created_at']
    list_filter = ['is_registered', 'class_name', 'created_at']
    search_fields = ['student_id', 'full_name', 'email']
    ordering = ['student_id']


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['student', 'session', 'date', 'time_in', 'status', 'confidence']
    list_filter = ['status', 'date', 'camera_id']
    search_fields = ['student__student_id', 'student__full_name']
    date_hierarchy = 'date'
    ordering = ['-date', '-time_in']


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ['camera_id', 'name', 'location', 'status', 'last_active']
    list_filter = ['status']
    search_fields = ['camera_id', 'name', 'location']


@admin.register(SystemStats)
class SystemStatsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_students', 'attendance_rate', 'total_scans']
    date_hierarchy = 'date'
    ordering = ['-date']


# =====================================================
# Quản lý Môn học
# =====================================================

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'teacher', 'credits']
    list_filter = ['credits']
    search_fields = ['code', 'name', 'teacher']
    ordering = ['code']


# =====================================================
# Quản lý Lớp học
# =====================================================

@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ['class_id', 'name', 'department', 'get_student_count']
    list_filter = ['department']
    search_fields = ['class_id', 'name', 'department']
    filter_horizontal = ['students']   # Widget chọn sinh viên dạng 2 cột
    ordering = ['class_id']

    def get_student_count(self, obj):
        return obj.students.count()
    get_student_count.short_description = 'Số sinh viên'


# =====================================================
# Quản lý Thời khóa biểu
# =====================================================

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['subject', 'classroom', 'get_day_name', 'start_period', 'end_period', 'room', 'is_active']
    list_filter = ['day_of_week', 'is_active', 'classroom']
    search_fields = ['subject__name', 'subject__code', 'classroom__name', 'room']
    ordering = ['day_of_week', 'start_period']
    list_editable = ['is_active']

    def get_day_name(self, obj):
        return obj.get_day_of_week_display()
    get_day_name.short_description = 'Thứ'
    get_day_name.admin_order_field = 'day_of_week'


# =====================================================
# Quản lý Buổi điểm danh
# =====================================================

@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_subject', 'get_classroom', 'date', 'status', 'get_present_count', 'get_total_students', 'start_time']
    list_filter = ['status', 'date', 'schedule__classroom']
    search_fields = ['schedule__subject__name', 'schedule__classroom__name']
    date_hierarchy = 'date'
    ordering = ['-date', '-created_at']
    readonly_fields = ['created_at', 'start_time', 'end_time']

    def get_subject(self, obj):
        return obj.schedule.subject.name
    get_subject.short_description = 'Môn học'
    get_subject.admin_order_field = 'schedule__subject__name'

    def get_classroom(self, obj):
        return obj.schedule.classroom.name
    get_classroom.short_description = 'Lớp học'

    def get_present_count(self, obj):
        return obj.get_present_count()
    get_present_count.short_description = 'Có mặt'

    def get_total_students(self, obj):
        return obj.get_total_students()
    get_total_students.short_description = 'Sĩ số'
