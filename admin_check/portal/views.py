from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg
from django.views.static import serve
from .models import Student, AttendanceRecord, Camera, SystemStats, Subject, ClassRoom, Schedule, AttendanceSession, Grade
from . import face_recognition as fr
from .attendance_import import import_csv_bytes
from .attendance_service import (
    METHOD_FACIAL_RECOGNITION,
    attendance_payload,
    calculate_attendance_status,
    get_session_scheduled_time,
    next_attendance_id,
    record_attendance_event,
    finalize_session_attendance,
    resolve_session,
    session_external_id,
)
import json
import cv2
import numpy as np
import base64
import os
import datetime
import csv
import hmac
import logging
from functools import wraps
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache

PORTAL_FRONTEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'APP', 'Portal'))
KIOSK_FRONTEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'APP', 'Máy điểm danh'))
logger = logging.getLogger(__name__)


def student_portal(request):
    """Serve the existing static portal on the same origin as Django APIs."""
    return serve(request, 'index.html', document_root=PORTAL_FRONTEND_ROOT)


def student_portal_asset(request, path):
    return serve(request, path, document_root=PORTAL_FRONTEND_ROOT)


def attendance_kiosk(request):
    """Serve the face kiosk on the same origin as the central API."""
    response = serve(request, 'index.html', document_root=KIOSK_FRONTEND_ROOT)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


def attendance_kiosk_asset(request, path):
    response = serve(request, path, document_root=KIOSK_FRONTEND_ROOT)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


def student_api_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


def admin_api_required(view):
    """Require an authenticated staff user for management mutations."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse({'success': False, 'error': 'Staff authentication required'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def kiosk_api_required(view):
    """Require the per-kiosk API key (or a staff session for local recovery)."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        supplied = request.headers.get('X-Kiosk-Key', '')
        if request.user.is_authenticated and request.user.is_staff:
            return view(request, *args, **kwargs)
        if not supplied or not hmac.compare_digest(supplied, settings.KIOSK_API_KEY):
            return JsonResponse({'success': False, 'error': 'Kiosk authentication required'}, status=401)
        bucket = f"kiosk-rate:{request.META.get('REMOTE_ADDR', 'unknown')}:{timezone.now():%Y%m%d%H%M}"
        try:
            count = cache.get(bucket, 0)
            if count >= 120:
                return JsonResponse({'success': False, 'error': 'Too many requests'}, status=429)
            cache.set(bucket, count + 1, timeout=120)
        except Exception:
            logger.warning('Kiosk rate limiter unavailable', exc_info=True)
        return view(request, *args, **kwargs)
    return wrapped


def home(request):
    """Management entry point. The kiosk runs as a separate application."""
    return redirect('portal:admin_dashboard')

    """Legacy portal landing page kept below for reference."""
    # Lấy thống kê
    total_students = Student.objects.count()
    
    # Tính tỷ lệ điểm danh hôm nay
    today = timezone.localdate()
    today_attendance = AttendanceRecord.objects.filter(
        date=today, 
        status__in=['present', 'late']
    ).count()
    
    if total_students > 0:
        attendance_rate = round((today_attendance / total_students) * 100, 1)
    else:
        attendance_rate = 0
    
    # Số camera đang hoạt động
    active_cameras = Camera.objects.filter(status='active').count()
    
    context = {
        'total_students': total_students,
        'attendance_rate': attendance_rate,
        'active_cameras': active_cameras,
        'avg_scan_time': None,
        'opencv_plugin_url': settings.OPENCV_PLUGIN_URL,
        'admin_url': settings.ADMIN_DASHBOARD_URL,
        'register_url': settings.REGISTER_FACE_URL,
    }
    return render(request, 'portal/home.html', context)


@staff_member_required(login_url='/admin/login/')
def admin_dashboard(request):
    """Trang Admin Dashboard"""
    from .face_recognition import load_database
    
    # Đếm số người đã đăng ký khuôn mặt từ face_database.pkl
    face_db = load_database()
    registered_faces = len(face_db)  # Số người đã đăng ký mặt
    
    # Thống kê tổng quan từ Student model
    total_students = Student.objects.count()
    
    today = timezone.localdate()
    today_records = AttendanceRecord.objects.filter(date=today)
    
    # Đếm số sinh viên unique có mặt hôm nay (không đếm trùng)
    today_attended_unique = today_records.filter(status__in=['present', 'late']).values('student').distinct().count()
    
    # Vắng = Tổng sinh viên - Có mặt unique (không được âm)
    today_absent = max(0, total_students - today_attended_unique)
    
    context = {
        'total_students': total_students,
        'today': today,
        'registered_students': registered_faces,  # Từ face_database.pkl
        'today_present': today_records.filter(status='present').values('student').distinct().count(),
        'today_late': today_records.filter(status='late').values('student').distinct().count(),
        'today_absent': today_absent,
        'recent_records': AttendanceRecord.objects.select_related('student').order_by('-date', '-time_in')[:20],
        'cameras': Camera.objects.all(),
        'students': Student.objects.all().order_by('-created_at'),  # Danh sách sinh viên
        'classrooms': ClassRoom.objects.all().order_by('class_id'),
    }
    return render(request, 'portal/admin_dashboard.html', context)


@staff_member_required(login_url='/admin/login/')
def register_face(request):
    """Compatibility route: face registration belongs to the admin workspace."""
    return redirect(f"{settings.ADMIN_DASHBOARD_URL}#face-registration")


def scan_camera(request):
    """
    Trang scan camera với nhận diện khuôn mặt real-time
    """
    students = Student.objects.filter(is_registered=True)
    context = {
        'students': students,
        'message': 'Điểm danh bằng nhận diện khuôn mặt'
    }
    return render(request, 'portal/scan_camera.html', context)


# =====================================================
# Thời khóa biểu và Điểm danh theo buổi
# =====================================================

def _open_today_sessions(today=None):
    """Ensure every class scheduled for today is ready for kiosk check-in."""
    today = today or timezone.localdate()
    schedules = Schedule.objects.filter(is_active=True, day_of_week=today.weekday())
    for schedule in schedules:
        session, created = AttendanceSession.objects.get_or_create(
            schedule=schedule,
            date=today,
            defaults={'status': 'active', 'start_time': timezone.now()},
        )
        if created or session.status in {'scheduled', 'cancelled'}:
            session.status = 'active'
            session.start_time = session.start_time or timezone.now()
            session.save(update_fields=['status', 'start_time'])
        session_external_id(session)


@staff_member_required(login_url='/admin/login/')
def schedule_view(request):
    """Trang thời khóa biểu - Chọn buổi học để điểm danh"""
    today = timezone.localdate()
    current_day = today.weekday()  # 0 = Monday, khớp với DAY_CHOICES

    # Lấy tất cả thời khóa biểu
    schedules = Schedule.objects.filter(is_active=True).select_related('subject', 'classroom')

    # Tạo dữ liệu thời khóa biểu theo ngày
    schedule_by_day = {}
    day_names_en = {
        0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday',
        4: 'Friday', 5: 'Saturday', 6: 'Sunday',
    }
    current_day_name = ''
    for day_num, day_name in Schedule.DAY_CHOICES:
        schedule_by_day[day_num] = {
            'name': day_name,
            'name_en': day_names_en[day_num],
            'schedules': schedules.filter(day_of_week=day_num)
        }
        if day_num == current_day:
            current_day_name = day_names_en[day_num]

    # Open today's scheduled classes automatically. The kiosk can therefore
    # receive attendance as soon as class time arrives, without a manual
    # "Start session" action in the management UI.
    _open_today_sessions(today)

    # Lấy các buổi điểm danh hôm nay
    today_sessions = AttendanceSession.objects.filter(date=today).select_related('schedule__subject', 'schedule__classroom')

    # Lấy các buổi đang hoạt động
    active_sessions = AttendanceSession.objects.filter(status='active').select_related('schedule__subject', 'schedule__classroom')

    context = {
        'schedule_by_day': schedule_by_day,
        'today': today,
        'current_day': current_day,
        'current_day_name': current_day_name,   # Tên thứ hiện tại (vd: "Thứ Ba")
        'today_sessions': today_sessions,
        'active_sessions': active_sessions,
        'subjects': Subject.objects.all(),
        'classrooms': ClassRoom.objects.all(),
    }
    return render(request, 'portal/schedule.html', context)


@staff_member_required(login_url='/admin/login/')
def start_attendance_session(request, schedule_id):
    """Bắt đầu buổi điểm danh từ thời khóa biểu"""
    schedule = get_object_or_404(Schedule, id=schedule_id)
    today = timezone.localdate()
    
    # Tạo hoặc lấy buổi điểm danh cho hôm nay
    session, created = AttendanceSession.objects.get_or_create(
        schedule=schedule,
        date=today,
        defaults={
            'status': 'active',
            'start_time': timezone.now()
        }
    )
    
    if not created:
        # Nếu đã tồn tại, chuyển sang trạng thái active
        session.status = 'active'
        session.start_time = timezone.now()
        session.save()

    session_external_id(session)
    
    return redirect('portal:attendance_session', session_id=session.id)


@staff_member_required(login_url='/admin/login/')
def attendance_session(request, session_id):
    """Trang điểm danh cho 1 buổi học cụ thể"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    # Lấy danh sách sinh viên trong lớp
    students_in_class = session.schedule.classroom.students.all()
    
    # Lấy các bản ghi điểm danh của buổi này
    attendance_records = list(session.session_records.select_related('student'))
    attended_ids = {record.student_id for record in attendance_records}
    records_by_student = {record.student_id: record for record in attendance_records}
    roster = [
        {'student': student, 'record': records_by_student.get(student.id)}
        for student in students_in_class
    ]
    
    context = {
        'session': session,
        'students_in_class': students_in_class,
        'attendance_records': attendance_records,
        'roster': roster,
        'attended_count': sum(1 for record in attendance_records if record.status in ('present', 'late')),
        'total_students': students_in_class.count(),
    }
    return render(request, 'portal/attendance_session.html', context)


@staff_member_required(login_url='/admin/login/')
def end_attendance_session(request, session_id):
    """Kết thúc buổi điểm danh"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    finalize_session_attendance(session)
    session.status = 'completed'
    session.end_time = timezone.now()
    session.save()
    return redirect('portal:schedule')


@admin_api_required
@require_http_methods(["POST"])
def api_finalize_session(request, session_id):
    """Close a session and persist absent rows for the complete class roster."""
    session = get_object_or_404(AttendanceSession, id=session_id)
    created = finalize_session_attendance(session)
    session.status = 'completed'
    session.end_time = timezone.now()
    session.save(update_fields=['status', 'end_time'])
    return JsonResponse({'success': True, 'data': {
        'session_id': session_external_id(session),
        'absent_created': created,
        'total_students': session.get_total_students(),
        'present_count': session.get_present_count(),
    }})


# =====================================================
# Video Streaming với Face Recognition
# =====================================================

# Lưu session_id hiện tại đang điểm danh (global variable)
_current_session_id = None

def set_current_session(session_id):
    global _current_session_id
    _current_session_id = session_id

def get_current_session():
    global _current_session_id
    return _current_session_id


def gen_frames(camera):
    """Generator để stream video frames với nhận diện khuôn mặt"""
    while True:
        frame = camera.get_frame()
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


def video_feed(request):
    """Stream video với nhận diện khuôn mặt"""
    session_id = request.GET.get('session_id')
    if session_id:
        set_current_session(int(session_id))
    camera = fr.VideoCamera()
    return StreamingHttpResponse(
        gen_frames(camera),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )


def video_feed_session(request, session_id):
    """Stream video cho buổi điểm danh cụ thể"""
    set_current_session(session_id)
    camera = fr.VideoCamera(session_id=session_id)
    return StreamingHttpResponse(
        gen_frames(camera),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )


# =====================================================
# API Endpoints
# =====================================================

@admin_api_required
@require_http_methods(["GET"])
def api_stats(request):
    """API trả về thống kê realtime"""
    total_students = Student.objects.count()
    today = timezone.localdate()
    today_attendance = AttendanceRecord.objects.filter(
        date=today,
        status__in=['present', 'late']
    ).count()
    
    attendance_rate = round((today_attendance / total_students) * 100, 1) if total_students else 0
    
    active_cameras = Camera.objects.filter(status='active').count()
    
    return JsonResponse({
        'success': True,
        'data': {
            'total_students': total_students,
            'attendance_rate': attendance_rate,
            'active_cameras': active_cameras,
            'avg_scan_time': None,
            'last_sync': timezone.now().strftime('%H:%M:%S'),
        }
    })


@kiosk_api_required
@csrf_exempt
@require_http_methods(["POST"])
def api_record_attendance(request):
    """
    API để plugin OpenCV gọi khi nhận diện được khuôn mặt
    
    Expected POST data:
    {
        "student_id": "SV001",
        "confidence": 98.5,
        "camera_id": "CAM01"
    }
    """
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        confidence = data.get('confidence', 0)
        camera_id = data.get('camera_id', '')
        
        # Tìm sinh viên
        try:
            student = Student.objects.get(student_id=student_id)
        except Student.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Student not found'
            }, status=404)
        
        # Tạo bản ghi điểm danh
        today = timezone.localdate()
        current_time = timezone.localtime().time()
        
        record, created = AttendanceRecord.objects.get_or_create(
            student=student,
            date=today,
            defaults={
                'time_in': current_time,
                'status': 'present',
                'confidence': confidence,
                'camera_id': camera_id,
            }
        )
        
        if not created:
            # Đã điểm danh rồi, cập nhật time_out
            record.time_out = current_time
            record.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Attendance recorded',
            'data': {
                'student_name': student.full_name,
                'student_id': student.student_id,
                'time': current_time.strftime('%H:%M:%S'),
                'status': record.status,
                'created': created
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception:
        logger.exception('Attendance API failure')
        return JsonResponse({'success': False, 'error': 'Attendance processing failed'}, status=500)


@require_http_methods(["GET"])
@admin_api_required
def api_students(request):
    """API lấy danh sách sinh viên"""
    students = Student.objects.all().values(
        'student_id', 'full_name', 'class_name', 'is_registered'
    )
    return JsonResponse({
        'success': True,
        'data': list(students)
    })


@require_http_methods(["GET"])
@admin_api_required
def api_attendance_today(request):
    """Attendance feed for management; optional date/subject/class filters."""
    date_text = request.GET.get('date', '')
    if date_text:
        try:
            today = datetime.date.fromisoformat(date_text)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'date must use YYYY-MM-DD'}, status=400)
    else:
        today = timezone.localdate()
    records = AttendanceRecord.objects.filter(date=today).select_related(
        'student', 'session__schedule__subject', 'session__schedule__classroom'
    )
    subject_id = request.GET.get('subject_id')
    class_id = request.GET.get('class_id')
    if subject_id:
        records = records.filter(session__schedule__subject__code=subject_id)
    if class_id:
        records = records.filter(session__schedule__classroom__class_id=class_id)
    
    data = []
    for r in records:
        schedule = r.session.schedule if r.session_id else None
        data.append({
            'attendance_id': r.attendance_id,
            'session_id': r.session.external_session_id if r.session_id else None,
            'student_id': r.student.student_id,
            'student_name': r.student.full_name,
            'class_id': schedule.classroom.class_id if schedule else r.student.class_name,
            'class_name': schedule.classroom.name if schedule else r.student.class_name,
            'subject_id': schedule.subject.code if schedule else None,
            'subject_name': schedule.subject.name if schedule else None,
            'scheduled_time': r.scheduled_time.strftime('%H:%M:%S') if r.scheduled_time else None,
            'check_in_time': r.time_in.strftime('%H:%M:%S') if r.time_in else None,
            'time_in': r.time_in.strftime('%H:%M:%S') if r.time_in else None,
            'late_minutes': r.late_minutes,
            'status': r.status,
            'attendance_code': r.attendance_code,
            'attendance_label': r.attendance_label,
            'attendance_periods': r.attendance_periods,
            'method': r.method,
            'device_id': r.device_id,
            'confidence': r.confidence,
        })
    
    return JsonResponse({
        'success': True,
        'date': str(today),
        'data': data
    })


def _current_student(request):
    if not request.user.is_authenticated:
        return None
    return Student.objects.filter(user=request.user).first()


@student_api_required
@require_http_methods(["GET"])
def api_student_profile(request):
    student = _current_student(request)
    if not student:
        return JsonResponse({'success': False, 'error': 'Student profile not linked'}, status=403)
    return JsonResponse({'success': True, 'data': {
        'student_id': student.student_id,
        'full_name': student.full_name,
        'email': student.email,
        'class_name': student.class_name,
        'is_registered': student.is_registered,
    }})


@student_api_required
@require_http_methods(["GET"])
def api_student_schedule_today(request):
    student = _current_student(request)
    if not student:
        return JsonResponse({'success': False, 'error': 'Student profile not linked'}, status=403)
    today = timezone.localdate()
    schedules = Schedule.objects.filter(
        is_active=True,
        day_of_week=today.weekday(),
        classroom__students=student,
    ).select_related('subject', 'classroom').distinct()
    return JsonResponse({'success': True, 'date': str(today), 'data': [{
        'schedule_id': schedule.id,
        'subject_id': schedule.subject.code,
        'subject_name': schedule.subject.name,
        'teacher': schedule.subject.teacher,
        'class_id': schedule.classroom.class_id,
        'classroom': schedule.classroom.name,
        'room': schedule.room,
        'start_period': schedule.start_period,
        'end_period': schedule.end_period,
        'time_range': schedule.get_time_range(),
    } for schedule in schedules]})


@student_api_required
@require_http_methods(["GET"])
def api_student_attendance(request):
    student = _current_student(request)
    if not student:
        return JsonResponse({'success': False, 'error': 'Student profile not linked'}, status=403)
    records = AttendanceRecord.objects.filter(student=student).select_related(
        'session__schedule__subject', 'session__schedule__classroom'
    )
    data = []
    for record in records:
        session = record.session
        data.append({
            'attendance_id': record.attendance_id,
            'session_id': session_external_id(session) if session else None,
            'date': str(record.date),
            'subject_id': session.schedule.subject.code if session else None,
            'subject_name': session.schedule.subject.name if session else None,
            'scheduled_time': record.scheduled_time.strftime('%H:%M:%S') if record.scheduled_time else None,
            'check_in_time': record.time_in.strftime('%H:%M:%S') if record.time_in else None,
            'late_minutes': record.late_minutes,
            'status': record.status,
            'attendance_code': record.attendance_code,
            'attendance_label': record.attendance_label,
            'attendance_periods': record.attendance_periods,
            'method': record.method,
            'device_id': record.device_id,
        })
    return JsonResponse({'success': True, 'data': data})


@student_api_required
@require_http_methods(["GET"])
def api_student_attendance_summary(request):
    student = _current_student(request)
    if not student:
        return JsonResponse({'success': False, 'error': 'Student profile not linked'}, status=403)
    records = AttendanceRecord.objects.filter(student=student)
    return JsonResponse({'success': True, 'data': {
        'total_records': records.count(),
        'on_time': records.filter(attendance_code='ON_TIME').count(),
        'late_level_1': records.filter(attendance_code='LATE_LEVEL_1').count(),
        'late_one_period': records.filter(attendance_code='LATE_ONE_PERIOD').count(),
        'absent_two_periods': records.filter(attendance_code='ABSENT_TWO_PERIODS').count(),
        'absent': records.filter(attendance_code='ABSENT').count(),
    }})


@student_api_required
@require_http_methods(["GET"])
def api_student_grades(request):
    """Return the authenticated student's grade ledger."""
    student = _current_student(request)
    if not student:
        return JsonResponse({'success': False, 'error': 'Student profile not linked'}, status=403)
    grades = Grade.objects.filter(student=student).select_related('subject')
    return JsonResponse({'success': True, 'data': [{
        'subject_id': grade.subject.code,
        'subject_name': grade.subject.name,
        'semester': grade.semester,
        'assessment_type': grade.assessment_type,
        'score': float(grade.score),
        'updated_at': grade.updated_at.isoformat(),
    } for grade in grades]})


@student_api_required
@require_http_methods(["GET"])
def api_student_subject_summary(request):
    """Aggregate attendance and grades per subject for Portal."""
    from .attendance_service import session_period_count

    student = _current_student(request)
    if not student:
        return JsonResponse({'success': False, 'error': 'Student profile not linked'}, status=403)
    records = list(AttendanceRecord.objects.filter(student=student).select_related('session__schedule__subject'))
    grades = list(Grade.objects.filter(student=student).select_related('subject'))
    subjects = {}
    for grade in grades:
        item = subjects.setdefault(grade.subject_id, {
            'subject_id': grade.subject.code, 'subject_name': grade.subject.name,
            'absent_periods': 0, 'late_periods': 0, 'late_events': 0,
            'grades': [],
        })
        item['grades'].append({
            'semester': grade.semester, 'assessment_type': grade.assessment_type,
            'score': float(grade.score),
        })
    for record in records:
        if not record.session_id:
            continue
        subject = record.session.schedule.subject
        item = subjects.setdefault(subject.id, {
            'subject_id': subject.code, 'subject_name': subject.name,
            'absent_periods': 0, 'late_periods': 0, 'late_events': 0,
            'grades': [],
        })
        periods = record.attendance_periods
        if record.status == 'absent':
            item['absent_periods'] += periods if periods is not None else session_period_count(record.session)
        elif record.status == 'late':
            item['late_events'] += 1
            item['late_periods'] += periods or 0
    for item in subjects.values():
        item['exam_prohibited'] = item['absent_periods'] > 3
        item['exam_status'] = 'EXAM PROHIBITED' if item['exam_prohibited'] else 'ELIGIBLE'
    return JsonResponse({'success': True, 'data': sorted(subjects.values(), key=lambda item: item['subject_id'])})


# =====================================================
# Face Recognition APIs
# =====================================================

@admin_api_required
@require_http_methods(["GET"])
def api_face_engine_status(request):
    """Expose dependency health so the registration page can explain failures."""
    status = fr.face_engine_status()
    return JsonResponse({'success': True, 'data': status}, status=200 if status['available'] else 503)

@admin_api_required
@require_http_methods(["POST"])
def api_register_face(request):
    """API đăng ký khuôn mặt từ ảnh base64"""
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        name = data.get('name')
        class_name = data.get('class_name', '')  # Lấy class_name
        email = data.get('email', '')  # Lấy email
        images_base64 = data.get('images', [])  # List of base64 images
        
        if not student_id or not name or not images_base64:
            return JsonResponse({
                'success': False,
                'code': 'VALIDATION_ERROR',
                'error': 'Vui lòng nhập mã sinh viên, họ tên và ít nhất một ảnh.'
            }, status=400)
        if not isinstance(images_base64, list) or len(images_base64) > 5:
            return JsonResponse({'success': False, 'code': 'VALIDATION_ERROR', 'error': 'At most 5 images may be registered.'}, status=400)

        engine = fr.face_engine_status()
        if not engine['available']:
            return JsonResponse({
                'success': False,
                'code': engine['code'],
                'error': engine['message'],
                'detail': engine.get('detail', ''),
            }, status=503)
        
        # Decode và xử lý ảnh
        registered_count = 0
        for img_b64 in images_base64:
            try:
                # Xóa header base64 nếu có
                if ',' in img_b64:
                    img_b64 = img_b64.split(',')[1]
                
                if not isinstance(img_b64, str) or len(img_b64) > 6 * 1024 * 1024:
                    continue
                img_data = base64.b64decode(img_b64, validate=True)
                nparr = np.frombuffer(img_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    success = fr.register_face(
                        name,
                        frame,
                        student_id=student_id,
                        class_name=class_name,
                        email=email,
                    )
                    if isinstance(success, tuple):
                        success = success[0]
                    if success:
                        registered_count += 1
            except RuntimeError as e:
                return JsonResponse({
                    'success': False,
                    'code': 'FACE_ENGINE_UNAVAILABLE',
                    'error': str(e),
                }, status=503)
            except Exception as e:
                print(f"Error processing image: {e}")
                continue
        
        if registered_count > 0:
            # Cập nhật student trong database với đầy đủ thông tin
            student, created = Student.objects.update_or_create(
                student_id=student_id,
                defaults={
                    'full_name': name,
                    'class_name': class_name,  # Lưu class_name
                    'email': email,  # Lưu email
                    'is_registered': True
                }
            )
            
            # Tự động thêm sinh viên vào ClassRoom nếu có class_name
            if class_name:
                from .models import ClassRoom
                classroom = ClassRoom.objects.filter(class_id__iexact=class_name).first()
                classroom = classroom or ClassRoom.objects.filter(name__iexact=class_name).first()
                if classroom:
                    classroom.students.add(student)
            
            return JsonResponse({
                'success': True,
                'message': f'Registered {registered_count} face(s) for {name}',
                'data': {
                    'student_id': student_id,
                    'name': name,
                    'faces_registered': registered_count
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'code': 'NO_FACE_DETECTED',
                'error': 'Không tìm thấy khuôn mặt rõ ràng trong ảnh đã chọn.'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'code': 'INVALID_JSON',
            'error': 'Invalid JSON'
        }, status=400)
    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'Face registration failed'
        }, status=500)


@admin_api_required
@require_http_methods(["DELETE"])
def api_delete_student(request, student_id):
    """API xóa sinh viên và dữ liệu khuôn mặt"""
    import shutil
    from .face_recognition import load_database, save_database, MY_FACES_DIR, face_folder_name
    
    try:
        # Lấy thông tin sinh viên
        student = Student.objects.get(id=student_id)
        student_name = student.full_name
        
        # 1. Xóa khỏi face_database.pkl
        face_db = load_database()
        removed = False
        for identity in (student.student_id, student_name):
            if identity in face_db:
                face_db.pop(identity, None)
                removed = True
        if removed:
            save_database(face_db)
        
        # 2. Xóa thư mục ảnh my_faces/{tên}
        import os
        person_dir = os.path.join(MY_FACES_DIR, face_folder_name(student_name, student.class_name))
        if os.path.exists(person_dir):
            shutil.rmtree(person_dir)
        
        # 3. Xóa các bản ghi điểm danh liên quan
        AttendanceRecord.objects.filter(student=student).delete()
        
        # 4. Xóa sinh viên khỏi database
        student.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Đã xóa sinh viên {student_name} và tất cả dữ liệu liên quan'
        })
        
    except Student.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Không tìm thấy sinh viên'
        }, status=404)
    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'Student deletion failed'
        }, status=500)


@admin_api_required
@require_http_methods(["PUT"])
def api_update_student(request, student_id):
    """API cập nhật thông tin sinh viên"""
    from .face_recognition import load_database, save_database, MY_FACES_DIR, face_folder_name
    import os
    import shutil
    
    try:
        data = json.loads(request.body)
        student = Student.objects.get(id=student_id)
        old_name = student.full_name
        
        # Cập nhật thông tin
        new_student_id = data.get('student_id', student.student_id)
        new_full_name = data.get('full_name', student.full_name)
        new_class_name = data.get('class_name', student.class_name)
        new_email = data.get('email', student.email)
        
        # Nếu tên thay đổi, cập nhật trong face_database.pkl và thư mục my_faces
        if new_full_name != old_name or new_class_name != student.class_name:
            # Cập nhật face_database.pkl
            face_db = load_database()
            identity = student.student_id if student.student_id in face_db else old_name
            if identity in face_db:
                face_db[student.student_id] = face_db.pop(identity)
                save_database(face_db)
            
            # Đổi tên thư mục my_faces
            old_dir = os.path.join(MY_FACES_DIR, face_folder_name(old_name, student.class_name))
            new_dir = os.path.join(MY_FACES_DIR, face_folder_name(new_full_name, new_class_name))
            if os.path.exists(old_dir):
                shutil.move(old_dir, new_dir)
        
        # Cập nhật student trong database
        student.student_id = new_student_id
        student.full_name = new_full_name
        student.class_name = new_class_name
        student.email = new_email
        student.save()

        # Keep the on-disk student profile in sync with the database.
        if student.is_registered:
            profile_dir = os.path.join(MY_FACES_DIR, face_folder_name(new_full_name, new_class_name))
            profile_path = os.path.join(profile_dir, 'student.json')
            if os.path.isdir(profile_dir):
                with open(profile_path, 'w', encoding='utf-8') as stream:
                    json.dump({
                        'student_id': new_student_id,
                        'full_name': new_full_name,
                        'class_name': new_class_name,
                        'email': new_email,
                        'face_files': sorted(
                            f for f in os.listdir(profile_dir)
                            if f.lower().endswith(('.jpg', '.jpeg', '.png'))
                        ),
                    }, stream, ensure_ascii=False, indent=2)
        
        return JsonResponse({
            'success': True,
            'message': f'Đã cập nhật thông tin sinh viên {new_full_name}'
        })
        
    except Student.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Không tìm thấy sinh viên'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'Student update failed'
        }, status=500)


@kiosk_api_required
@csrf_exempt
@require_http_methods(["POST"])
def api_recognize_face(request):
    """Recognize one camera frame and persist the canonical attendance event."""
    try:
        data = json.loads(request.body)
        image_base64 = data.get('image')
        session_ref = data.get('session_id')
        device_id = str(data.get('device_id') or 'KIOSK-LOCAL')[:80]
        
        if not image_base64:
            return JsonResponse({
                'success': False,
                'error': 'Missing image'
            }, status=400)
        
        # Xóa header base64 nếu có
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]
        
        if not isinstance(image_base64, str) or len(image_base64) > 6 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'Image exceeds 4 MB limit'}, status=413)
        img_data = base64.b64decode(image_base64, validate=True)
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return JsonResponse({
                'success': False,
                'error': 'Invalid image data'
            }, status=400)
        
        # Nhận diện khuôn mặt qua InsightFace
        results = fr.recognize_frame(frame)
        now = timezone.localtime()
        today = now.date()
        current_time = now.time()

        try:
            session_obj = resolve_session(session_ref) if session_ref else None
        except AttendanceSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Session not found'}, status=404)

        if session_obj and session_obj.status != 'active':
            return JsonResponse({'success': False, 'error': 'Session is not active'}, status=409)

        recognized = []
        canonical = None

        for item in results:
            name = item.get('name', 'Unknown')
            conf = item.get('confidence', 0.0)
            bbox = item.get('bbox', [])
            
            face_info = {
                'name': name,
                'confidence': round(conf, 1),
                'bbox': bbox,
                'student_id': '',
                'class_name': '',
                'status': 'unknown',
                'is_new_attendance': False
            }
            
            if name != "Unknown":
                student = Student.objects.filter(full_name__iexact=name).first()
                if not student:
                    student = Student.objects.filter(student_id__iexact=name).first()
                
                if student:
                    face_info['student_id'] = student.student_id
                    face_info['class_name'] = student.class_name
                    face_info['name'] = student.full_name
                    
                    if session_obj is None:
                        return JsonResponse({'success': False, 'error': 'An active session is required'}, status=409)
                    enrolled = session_obj.schedule.classroom.students.filter(pk=student.pk).exists()
                    if not enrolled:
                        face_info.update({
                            'status': 'wrong_class',
                            'attendance_code': 'WRONG_CLASS',
                            'attendance_label': 'NHẦM LỚP',
                            'error': 'Student is not enrolled in this class session',
                            'is_new_attendance': False,
                            'already_checked_in': False,
                        })
                        recognized.append(face_info)
                        continue
                    try:
                        record, created, timing = record_attendance_event(
                            session=session_obj,
                            student=student,
                            check_in_at=current_time,
                            confidence=conf / 100.0,
                            method=METHOD_FACIAL_RECOGNITION,
                            device_id=device_id,
                        )
                    except ValueError as error:
                        return JsonResponse({'success': False, 'error': str(error)}, status=409)

                    face_info['status'] = record.status
                    face_info['attendance_code'] = record.attendance_code or timing['attendance_code']
                    face_info['attendance_label'] = record.attendance_label or timing['attendance_label']
                    face_info['late_minutes'] = record.late_minutes
                    face_info['attendance_periods'] = record.attendance_periods
                    face_info['is_new_attendance'] = created
                    face_info['already_checked_in'] = not created
                    face_info['time_in'] = record.time_in.strftime('%H:%M:%S') if record.time_in else current_time.strftime('%H:%M:%S')
                    canonical = (student, record, created)
            
            recognized.append(face_info)
        
        response = {
            'success': True,
            'data': {
                'faces_detected': len(results),
                'recognized': recognized,
                'timestamp': now.strftime('%H:%M:%S')
            }
        }
        if canonical:
            student, record, created = canonical
            response.update({
                'student': {'student_id': student.student_id, 'full_name': student.full_name},
                'session': {
                    'session_id': session_external_id(session_obj) if session_obj else None,
                    'subject_id': session_obj.schedule.subject.code if session_obj else None,
                    'subject_name': session_obj.schedule.subject.name if session_obj else None,
                    'scheduled_time': record.scheduled_time.strftime('%H:%M:%S') if record.scheduled_time else None,
                },
                'attendance': attendance_payload(record, session_obj, already_checked_in=not created),
            })
        return JsonResponse(response)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'Face recognition failed'
        }, status=500)


@require_http_methods(["GET"])
@admin_api_required
def api_registered_faces(request):
    """API lấy danh sách khuôn mặt đã đăng ký"""
    database = fr.load_database()
    
    faces = []
    for name, embeddings in database.items():
        faces.append({
            'name': name,
            'embeddings_count': len(embeddings)
        })
    
    return JsonResponse({
        'success': True,
        'data': faces
    })


# =====================================================
# API cho Thời khóa biểu và Buổi điểm danh
# =====================================================

@require_http_methods(["GET"])
@admin_api_required
def api_schedules(request):
    """API lấy thời khóa biểu"""
    day = request.GET.get('day')
    schedules = Schedule.objects.filter(is_active=True).select_related('subject', 'classroom')
    
    if day is not None:
        schedules = schedules.filter(day_of_week=int(day))
    
    data = [{
        'id': s.id,
        'subject': s.subject.name,
        'subject_code': s.subject.code,
        'classroom': s.classroom.name,
        'class_id': s.classroom.class_id,
        'day_of_week': s.day_of_week,
        'day_name': s.get_day_of_week_display(),
        'start_period': s.start_period,
        'end_period': s.end_period,
        'time_range': s.get_time_range(),
        'room': s.room,
    } for s in schedules]
    
    return JsonResponse({'success': True, 'data': data})


@require_http_methods(["GET"])
@kiosk_api_required
def api_sessions_today(request):
    """API lấy các buổi điểm danh hôm nay"""
    today = timezone.localdate()
    _open_today_sessions(today)
    sessions = AttendanceSession.objects.filter(date=today).select_related('schedule__subject', 'schedule__classroom')
    
    data = [{
        'id': s.id,
        'session_id': session_external_id(s),
        'subject': s.schedule.subject.name,
        'classroom': s.schedule.classroom.name,
        'date': str(s.date),
        'status': s.status,
        'status_display': s.get_status_display(),
        'present_count': s.get_present_count(),
        'total_students': s.get_total_students(),
        'start_time': s.start_time.strftime('%H:%M:%S') if s.start_time else None,
        'scheduled_time': get_session_scheduled_time(s).strftime('%H:%M:%S'),
        'room': s.schedule.room,
    } for s in sessions]
    
    return JsonResponse({'success': True, 'data': data})


@require_http_methods(["GET"])
@admin_api_required
def api_session_attendance(request, session_id):
    """API lấy danh sách điểm danh của 1 buổi"""
    try:
        session = AttendanceSession.objects.get(id=session_id)
        records = session.session_records.select_related('student')
        
        data = [{
            'attendance_id': r.attendance_id,
            'student_id': r.student.student_id,
            'student_name': r.student.full_name,
            'class_name': r.student.class_name,
            'time_in': r.time_in.strftime('%H:%M:%S') if r.time_in else None,
            'status': r.status,
            'confidence': round(r.confidence * 100, 1) if r.confidence else 0,
            'scheduled_time': r.scheduled_time.strftime('%H:%M:%S') if r.scheduled_time else None,
            'late_minutes': r.late_minutes,
            'attendance_code': r.attendance_code,
            'attendance_label': r.attendance_label,
            'attendance_periods': r.attendance_periods,
            'method': r.method,
            'device_id': r.device_id,
        } for r in records]
        
        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'session_id': session_external_id(session),
                'subject': session.schedule.subject.name,
                'classroom': session.schedule.classroom.name,
                'class_id': session.schedule.classroom.class_id,
                'date': str(session.date),
                'status': session.status,
                'scheduled_time': get_session_scheduled_time(session).strftime('%H:%M:%S'),
            },
            'data': data
        })
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Session not found'}, status=404)


def _session_roster_rows(session):
    students = session.schedule.classroom.students.all().order_by('student_id')
    records = {record.student_id: record for record in session.session_records.select_related('student')}
    scheduled_time = get_session_scheduled_time(session)
    rows = []
    for student in students:
        record = records.get(student.id)
        if record:
            row = {
                'attendance_id': record.attendance_id,
                'student_id': student.student_id,
                'student_name': student.full_name,
                'class_id': session.schedule.classroom.class_id,
                'subject_id': session.schedule.subject.code,
                'subject_name': session.schedule.subject.name,
                'date': str(session.date),
                'scheduled_time': record.scheduled_time.strftime('%H:%M:%S') if record.scheduled_time else scheduled_time.strftime('%H:%M:%S'),
                'check_in_time': record.time_in.strftime('%H:%M:%S') if record.time_in else None,
                'late_minutes': record.late_minutes,
                'status': record.status,
                'attendance_code': record.attendance_code,
                'attendance_label': record.attendance_label,
                'attendance_periods': record.attendance_periods,
                'method': record.method,
                'device_id': record.device_id,
                'already_checked_in': True,
            }
        else:
            closed = session.status in ('completed', 'cancelled')
            row = {
                'attendance_id': None,
                'student_id': student.student_id,
                'student_name': student.full_name,
                'class_id': session.schedule.classroom.class_id,
                'subject_id': session.schedule.subject.code,
                'subject_name': session.schedule.subject.name,
                'date': str(session.date),
                'scheduled_time': scheduled_time.strftime('%H:%M:%S'),
                'check_in_time': None,
                'late_minutes': None,
                'status': 'absent' if closed else 'not_checked_in',
                'attendance_code': 'ABSENT' if closed else 'NOT_CHECKED_IN',
                'attendance_label': 'VẮNG' if closed else 'CHƯA ĐIỂM DANH',
                'attendance_periods': None,
                'method': None,
                'device_id': None,
                'already_checked_in': False,
            }
        rows.append(row)
    return rows


@require_http_methods(["GET"])
@kiosk_api_required
def api_session_roster(request, session_id):
    """Return every expected student, including students not yet scanned."""
    try:
        session = AttendanceSession.objects.select_related('schedule__subject', 'schedule__classroom').get(id=session_id)
        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'session_id': session_external_id(session),
                'subject_id': session.schedule.subject.code,
                'subject_name': session.schedule.subject.name,
                'class_id': session.schedule.classroom.class_id,
                'classroom': session.schedule.classroom.name,
                'room': session.schedule.room,
                'date': str(session.date),
                'scheduled_time': get_session_scheduled_time(session).strftime('%H:%M:%S'),
                'status': session.status,
            },
            'data': _session_roster_rows(session),
        })
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Session not found'}, status=404)


@require_http_methods(["GET"])
@admin_api_required
def api_export_session_csv(request, session_id):
    """Export a session roster as UTF-8 BOM CSV for Excel compatibility."""
    try:
        session = AttendanceSession.objects.select_related('schedule__subject', 'schedule__classroom').get(id=session_id)
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Session not found'}, status=404)

    columns = [
        'attendance_id', 'session_id', 'student_id', 'student_name', 'class_id',
        'subject_id', 'subject_name', 'date', 'scheduled_time', 'check_in_time',
        'late_minutes', 'status', 'attendance_code', 'attendance_label',
        'attendance_periods', 'method', 'device_id',
    ]
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response.write('\ufeff')
    response['Content-Disposition'] = f'attachment; filename="attendance-{session.date}-{session.id}.csv"'
    writer = csv.DictWriter(response, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    for row in _session_roster_rows(session):
        row['session_id'] = session_external_id(session)
        writer.writerow(row)
    return response


@admin_api_required
@require_http_methods(["POST"])
def api_import_attendance_csv(request):
    """Administrative CSV backup import into the same central records."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Staff authentication required'}, status=403)
    uploaded = request.FILES.get('file')
    if uploaded is None:
        return JsonResponse({'success': False, 'error': 'Missing multipart file field: file'}, status=400)
    result = import_csv_bytes(uploaded.read(), source=uploaded.name)
    status = 200 if result.imported or result.duplicates else 400
    return JsonResponse({
        'success': status == 200 and not result.failed,
        'data': {
            'file': uploaded.name,
            'imported': result.imported,
            'duplicates': result.duplicates,
            'failed': result.failed,
        },
    }, status=status)


@kiosk_api_required
@csrf_exempt
@require_http_methods(["POST"])
def api_record_session_attendance(request):
    """API ghi nhận điểm danh cho 1 buổi học"""
    try:
        data = json.loads(request.body)
        session_ref = data.get('session_id')
        student_name = data.get('student_name')
        confidence = data.get('confidence', 0)
        device_id = data.get('device_id', 'MANUAL-MANAGEMENT')
        
        if not session_ref or not student_name:
            return JsonResponse({
                'success': False,
                'error': 'Missing session_id or student_name'
            }, status=400)
        
        session = resolve_session(session_ref)
        student = Student.objects.get(full_name__iexact=student_name)
        record, created, timing = record_attendance_event(
            session=session,
            student=student,
            confidence=confidence,
            method=METHOD_FACIAL_RECOGNITION,
            device_id=device_id,
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{student.full_name} attendance recorded: {timing["attendance_label"]}',
            'data': {
                'student_name': student.full_name,
                'student_id': student.student_id,
                'class_name': student.class_name,
                'attendance_id': record.attendance_id,
                'time_in': record.time_in.strftime('%H:%M:%S') if record.time_in else None,
                'date': str(record.date),
                'session_id': session_external_id(session),
                'subject': session.schedule.subject.name,
                'created': created,
                'already_checked_in': not created,
                'status': record.status,
                'attendance_label': record.attendance_label,
                'attendance_code': record.attendance_code,
                'late_minutes': record.late_minutes,
                'attendance_periods': record.attendance_periods,
                'method': record.method,
                'device_id': record.device_id,
            }
        })
        
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Session not found'}, status=404)
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=409)
    except Exception:
        logger.exception('Session attendance API failure')
        return JsonResponse({'success': False, 'error': 'Attendance processing failed'}, status=500)


@admin_api_required
@require_http_methods(["POST"])
def api_create_session(request):
    """API tạo buổi điểm danh mới"""
    try:
        data = json.loads(request.body)
        schedule_id = data.get('schedule_id')
        date_str = data.get('date')  # Format: YYYY-MM-DD
        
        if not schedule_id:
            return JsonResponse({
                'success': False,
                'error': 'Missing schedule_id'
            }, status=400)
        
        schedule = Schedule.objects.get(id=schedule_id)
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localdate()
        
        session, created = AttendanceSession.objects.get_or_create(
            schedule=schedule,
            date=date,
            defaults={
                'status': 'active',
                'start_time': timezone.now()
            }
        )
        
        if not created:
            session.status = 'active'
            session.start_time = timezone.now()
            session.save()

        external_id = session_external_id(session)
        
        return JsonResponse({
            'success': True,
            'message': 'Đã tạo buổi điểm danh',
            'data': {
                'session_id': session.id,
                'external_session_id': external_id,
                'subject': schedule.subject.name,
                'classroom': schedule.classroom.name,
                'scheduled_time': get_session_scheduled_time(session).strftime('%H:%M:%S'),
                'date': str(date),
                'created': created
            }
        })
        
    except Schedule.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Schedule not found'}, status=404)
    except Exception:
        logger.exception('Session creation API failure')
        return JsonResponse({'success': False, 'error': 'Session creation failed'}, status=500)


@admin_api_required
@require_http_methods(["POST"])
def api_create_class(request):
    """Create a class and optionally attach existing students by ID."""
    try:
        data = json.loads(request.body or '{}')
        class_id = str(data.get('class_id') or '').strip()
        name = str(data.get('name') or '').strip()
        if not class_id or not name:
            return JsonResponse({'success': False, 'error': 'class_id and name are required'}, status=400)
        classroom, created = ClassRoom.objects.get_or_create(
            class_id=class_id,
            defaults={'name': name, 'department': str(data.get('department') or '').strip()},
        )
        if not created:
            classroom.name = name
            classroom.department = str(data.get('department') or classroom.department).strip()
            classroom.save(update_fields=['name', 'department'])
        student_ids = [str(value).strip() for value in (data.get('student_ids') or []) if str(value).strip()]
        if student_ids:
            classroom.students.add(*Student.objects.filter(student_id__in=student_ids))
        return JsonResponse({'success': True, 'created': created, 'data': {
            'id': classroom.id, 'class_id': classroom.class_id, 'name': classroom.name,
            'department': classroom.department, 'student_count': classroom.students.count(),
        }}, status=201 if created else 200)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@admin_api_required
@require_http_methods(["POST"])
def api_create_subject(request):
    """Create or update a subject from the Admin scheduling workspace."""
    try:
        data = json.loads(request.body or '{}')
        code = str(data.get('code') or '').strip().upper()
        name = str(data.get('name') or '').strip()
        if not code or not name:
            return JsonResponse({'success': False, 'error': 'Subject code and name are required'}, status=400)
        try:
            credits = int(data.get('credits') or 3)
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Credits must be a number'}, status=400)
        if credits < 1 or credits > 20:
            return JsonResponse({'success': False, 'error': 'Credits must be between 1 and 20'}, status=400)
        subject, created = Subject.objects.get_or_create(
            code=code,
            defaults={'name': name, 'teacher': str(data.get('teacher') or '').strip(), 'credits': credits},
        )
        if not created:
            subject.name = name
            subject.teacher = str(data.get('teacher') or '').strip()
            subject.credits = credits
            subject.save(update_fields=['name', 'teacher', 'credits'])
        return JsonResponse({'success': True, 'created': created, 'data': {
            'id': subject.id, 'code': subject.code, 'name': subject.name,
            'teacher': subject.teacher, 'credits': subject.credits,
        }}, status=201 if created else 200)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)


@admin_api_required
@require_http_methods(["POST"])
def api_create_schedule(request):
    """Attach a subject to a class and create/update its weekly schedule."""
    try:
        data = json.loads(request.body or '{}')
        subject_id = data.get('subject_id')
        classroom_id = data.get('classroom_id')
        if not subject_id or not classroom_id:
            return JsonResponse({'success': False, 'error': 'Subject and class are required'}, status=400)
        subject = Subject.objects.get(id=int(subject_id))
        classroom = ClassRoom.objects.get(id=int(classroom_id))
        day_of_week = int(data.get('day_of_week'))
        start_period = int(data.get('start_period'))
        end_period = int(data.get('end_period'))
        if day_of_week not in range(7):
            raise ValueError('Day of week must be between 0 and 6')
        if start_period not in range(1, 11) or end_period not in range(1, 11) or end_period < start_period:
            raise ValueError('Invalid teaching periods')
        schedule, created = Schedule.objects.get_or_create(
            subject=subject,
            classroom=classroom,
            day_of_week=day_of_week,
            start_period=start_period,
            end_period=end_period,
            defaults={'room': str(data.get('room') or '').strip(), 'is_active': True},
        )
        if not created:
            schedule.room = str(data.get('room') or '').strip()
            schedule.is_active = True
            schedule.save(update_fields=['room', 'is_active'])
        return JsonResponse({'success': True, 'created': created, 'data': {
            'id': schedule.id, 'subject_id': subject.id, 'subject': subject.name,
            'classroom_id': classroom.id, 'classroom': classroom.name,
            'day_of_week': schedule.day_of_week, 'start_period': schedule.start_period,
            'end_period': schedule.end_period, 'room': schedule.room,
        }}, status=201 if created else 200)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except (Subject.DoesNotExist, ClassRoom.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Subject or class not found'}, status=404)
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid subject, class, or period values'}, status=400)


@admin_api_required
@require_http_methods(["POST"])
def api_postpone_session(request, session_id):
    """Postpone a session without deleting its attendance history."""
    session = get_object_or_404(AttendanceSession, id=session_id)
    try:
        data = json.loads(request.body or '{}')
        postponed_to = data.get('postponed_to')
        if postponed_to:
            postponed_to = datetime.date.fromisoformat(str(postponed_to))
            if postponed_to <= session.date:
                return JsonResponse({'success': False, 'error': 'postponed_to must be after the current session date'}, status=400)
        session.status = 'postponed'
        session.postponed_to = postponed_to
        session.postponed_reason = str(data.get('reason') or '').strip()[:240]
        session.save(update_fields=['status', 'postponed_to', 'postponed_reason'])
        rescheduled = None
        if postponed_to:
            rescheduled, _ = AttendanceSession.objects.get_or_create(
                schedule=session.schedule,
                date=postponed_to,
                defaults={'status': 'scheduled', 'notes': f'Rescheduled from {session.date}.'},
            )
            session_external_id(rescheduled)
        return JsonResponse({'success': True, 'data': {
            'session_id': session_external_id(session), 'status': session.status,
            'postponed_to': str(session.postponed_to) if session.postponed_to else None,
            'rescheduled_session_id': session_external_id(rescheduled) if rescheduled else None,
        }})
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'postponed_to must use YYYY-MM-DD'}, status=400)


@admin_api_required
@require_http_methods(["GET"])
def api_export_all_csv(request):
    """Export students, classes, schedules, sessions and attendance in one CSV."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="uth-attendance-export.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    columns = ['entity_type', 'student_id', 'student_name', 'email', 'class_id', 'class_name', 'department', 'subject_id', 'subject_name', 'session_id', 'session_date', 'session_status', 'postponed_to', 'postponed_reason', 'scheduled_time', 'attendance_id', 'check_in_time', 'late_minutes', 'attendance_status', 'attendance_code', 'attendance_periods', 'method', 'device_id', 'semester', 'assessment_type', 'score']
    writer.writerow(columns)
    for student in Student.objects.order_by('student_id'):
        writer.writerow(['STUDENT', student.student_id, student.full_name, student.email, student.class_name, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
    for classroom in ClassRoom.objects.order_by('class_id'):
        writer.writerow(['CLASS', '', '', '', classroom.class_id, classroom.name, classroom.department, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
    for schedule in Schedule.objects.select_related('subject', 'classroom').order_by('id'):
        writer.writerow(['SCHEDULE', '', '', '', schedule.classroom.class_id, schedule.classroom.name, schedule.classroom.department, schedule.subject.code, schedule.subject.name, '', '', '', '', '', schedule.get_time_range(), '', '', '', '', '', '', '', '', '', '', ''])
    for session in AttendanceSession.objects.select_related('schedule__subject', 'schedule__classroom').order_by('-date', 'id'):
        writer.writerow(['SESSION', '', '', '', session.schedule.classroom.class_id, session.schedule.classroom.name, session.schedule.classroom.department, session.schedule.subject.code, session.schedule.subject.name, session_external_id(session), session.date, session.status, session.postponed_to or '', session.postponed_reason, get_session_scheduled_time(session), '', '', '', '', '', '', '', '', '', '', ''])
    for record in AttendanceRecord.objects.select_related('student', 'session__schedule__subject', 'session__schedule__classroom').order_by('-date', 'id'):
        schedule = record.session.schedule if record.session_id else None
        writer.writerow(['ATTENDANCE', record.student.student_id, record.student.full_name, record.student.email, schedule.classroom.class_id if schedule else record.student.class_name, schedule.classroom.name if schedule else '', schedule.classroom.department if schedule else '', schedule.subject.code if schedule else '', schedule.subject.name if schedule else '', session_external_id(record.session) if record.session_id else '', record.date, record.session.status if record.session_id else '', record.session.postponed_to if record.session_id and record.session.postponed_to else '', record.session.postponed_reason if record.session_id else '', record.scheduled_time or '', record.attendance_id or '', record.time_in or '', record.late_minutes, record.status, record.attendance_code, record.attendance_periods if record.attendance_periods is not None else '', record.method, record.device_id, '', '', ''])
    for grade in Grade.objects.select_related('student', 'subject').order_by('student__student_id', 'subject__code'):
        writer.writerow(['GRADE', grade.student.student_id, grade.student.full_name, grade.student.email, grade.student.class_name, '', '', grade.subject.code, grade.subject.name, '', '', '', '', '', '', '', '', '', '', '', '', '', '', grade.semester, grade.assessment_type, grade.score])
    return response
