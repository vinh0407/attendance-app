from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg
from .models import Student, AttendanceRecord, Camera, SystemStats, Subject, ClassRoom, Schedule, AttendanceSession
from . import face_recognition as fr
import json
import cv2
import numpy as np
import base64
import os
import datetime


def home(request):
    """Trang chủ - Portal chính"""
    # Lấy thống kê
    total_students = Student.objects.count()
    
    # Tính tỷ lệ điểm danh hôm nay
    today = timezone.now().date()
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
        'total_students': total_students or 1248,  # Default value nếu chưa có data
        'attendance_rate': attendance_rate or 96.4,
        'active_cameras': active_cameras or 8,
        'avg_scan_time': 0.8,
        'opencv_plugin_url': settings.OPENCV_PLUGIN_URL,
        'admin_url': settings.ADMIN_DASHBOARD_URL,
        'register_url': settings.REGISTER_FACE_URL,
    }
    return render(request, 'portal/home.html', context)


def admin_dashboard(request):
    """Trang Admin Dashboard"""
    from .face_recognition import load_database
    
    # Đếm số người đã đăng ký khuôn mặt từ face_database.pkl
    face_db = load_database()
    registered_faces = len(face_db)  # Số người đã đăng ký mặt
    
    # Thống kê tổng quan từ Student model
    total_students = Student.objects.count()
    
    today = timezone.now().date()
    today_records = AttendanceRecord.objects.filter(date=today)
    
    # Đếm số sinh viên unique có mặt hôm nay (không đếm trùng)
    today_present_unique = today_records.filter(status='present').values('student').distinct().count()
    
    # Vắng = Tổng sinh viên - Có mặt unique (không được âm)
    today_absent = max(0, total_students - today_present_unique)
    
    context = {
        'total_students': total_students,
        'registered_students': registered_faces,  # Từ face_database.pkl
        'today_present': today_present_unique,  # Số sinh viên unique
        'today_late': today_records.filter(status='late').values('student').distinct().count(),
        'today_absent': today_absent,
        'recent_records': AttendanceRecord.objects.select_related('student').order_by('-date', '-time_in')[:20],
        'cameras': Camera.objects.all(),
        'students': Student.objects.all().order_by('-created_at'),  # Danh sách sinh viên
    }
    return render(request, 'portal/admin_dashboard.html', context)


def register_face(request):
    """Trang đăng ký khuôn mặt mới"""
    context = {
        'opencv_plugin_url': settings.OPENCV_PLUGIN_URL,
    }
    return render(request, 'portal/register.html', context)


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

def schedule_view(request):
    """Trang thời khóa biểu - Chọn buổi học để điểm danh"""
    today = timezone.now().date()
    current_day = today.weekday()  # 0 = Monday, khớp với DAY_CHOICES

    # Lấy tất cả thời khóa biểu
    schedules = Schedule.objects.filter(is_active=True).select_related('subject', 'classroom')

    # Tạo dữ liệu thời khóa biểu theo ngày
    schedule_by_day = {}
    current_day_name = ''
    for day_num, day_name in Schedule.DAY_CHOICES:
        schedule_by_day[day_num] = {
            'name': day_name,
            'schedules': schedules.filter(day_of_week=day_num)
        }
        if day_num == current_day:
            current_day_name = day_name

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


def start_attendance_session(request, schedule_id):
    """Bắt đầu buổi điểm danh từ thời khóa biểu"""
    schedule = get_object_or_404(Schedule, id=schedule_id)
    today = timezone.now().date()
    
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
    
    return redirect('portal:attendance_session', session_id=session.id)


def attendance_session(request, session_id):
    """Trang điểm danh cho 1 buổi học cụ thể"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    # Lấy danh sách sinh viên trong lớp
    students_in_class = session.schedule.classroom.students.all()
    
    # Lấy các bản ghi điểm danh của buổi này
    attendance_records = session.session_records.select_related('student')
    attended_ids = attendance_records.values_list('student_id', flat=True)
    
    context = {
        'session': session,
        'students_in_class': students_in_class,
        'attendance_records': attendance_records,
        'attended_count': attendance_records.filter(status='present').count(),
        'total_students': students_in_class.count(),
    }
    return render(request, 'portal/attendance_session.html', context)


def end_attendance_session(request, session_id):
    """Kết thúc buổi điểm danh"""
    session = get_object_or_404(AttendanceSession, id=session_id)
    session.status = 'completed'
    session.end_time = timezone.now()
    session.save()
    return redirect('portal:schedule')


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

@require_http_methods(["GET"])
def api_stats(request):
    """API trả về thống kê realtime"""
    total_students = Student.objects.count() or 1248
    today = timezone.now().date()
    today_attendance = AttendanceRecord.objects.filter(
        date=today,
        status__in=['present', 'late']
    ).count()
    
    if total_students > 0:
        attendance_rate = round((today_attendance / total_students) * 100, 1)
    else:
        attendance_rate = 96.4
    
    active_cameras = Camera.objects.filter(status='active').count() or 8
    
    return JsonResponse({
        'success': True,
        'data': {
            'total_students': total_students,
            'attendance_rate': attendance_rate,
            'active_cameras': active_cameras,
            'avg_scan_time': 0.8,
            'last_sync': timezone.now().strftime('%H:%M:%S'),
        }
    })


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
        today = timezone.now().date()
        current_time = timezone.now().time()
        
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
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
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
def api_attendance_today(request):
    """API lấy danh sách điểm danh hôm nay"""
    today = timezone.now().date()
    records = AttendanceRecord.objects.filter(date=today).select_related('student')
    
    data = [{
        'student_id': r.student.student_id,
        'student_name': r.student.full_name,
        'time_in': r.time_in.strftime('%H:%M:%S') if r.time_in else None,
        'status': r.status,
        'confidence': r.confidence,
    } for r in records]
    
    return JsonResponse({
        'success': True,
        'date': str(today),
        'data': data
    })


# =====================================================
# Face Recognition APIs
# =====================================================

@csrf_exempt
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
                'error': 'Missing student_id, name, or images'
            }, status=400)
        
        # Decode và xử lý ảnh
        registered_count = 0
        for img_b64 in images_base64:
            try:
                # Xóa header base64 nếu có
                if ',' in img_b64:
                    img_b64 = img_b64.split(',')[1]
                
                img_data = base64.b64decode(img_b64)
                nparr = np.frombuffer(img_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    success = fr.register_face(name, frame)
                    if success:
                        registered_count += 1
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
                try:
                    classroom = ClassRoom.objects.get(class_id=class_name)
                    classroom.students.add(student)
                except ClassRoom.DoesNotExist:
                    pass  # Lớp không tồn tại thì bỏ qua
            
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
                'error': 'No faces detected in provided images'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def api_delete_student(request, student_id):
    """API xóa sinh viên và dữ liệu khuôn mặt"""
    import shutil
    from .face_recognition import load_database, save_database, MY_FACES_DIR
    
    try:
        # Lấy thông tin sinh viên
        student = Student.objects.get(id=student_id)
        student_name = student.full_name
        
        # 1. Xóa khỏi face_database.pkl
        face_db = load_database()
        if student_name in face_db:
            del face_db[student_name]
            save_database(face_db)
        
        # 2. Xóa thư mục ảnh my_faces/{tên}
        import os
        person_dir = os.path.join(MY_FACES_DIR, student_name)
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
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["PUT"])
def api_update_student(request, student_id):
    """API cập nhật thông tin sinh viên"""
    from .face_recognition import load_database, save_database, MY_FACES_DIR
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
        if new_full_name != old_name:
            # Cập nhật face_database.pkl
            face_db = load_database()
            if old_name in face_db:
                face_db[new_full_name] = face_db.pop(old_name)
                save_database(face_db)
            
            # Đổi tên thư mục my_faces
            old_dir = os.path.join(MY_FACES_DIR, old_name)
            new_dir = os.path.join(MY_FACES_DIR, new_full_name)
            if os.path.exists(old_dir):
                shutil.move(old_dir, new_dir)
                # Đổi tên các file ảnh trong thư mục
                for i, filename in enumerate(os.listdir(new_dir), 1):
                    old_path = os.path.join(new_dir, filename)
                    ext = os.path.splitext(filename)[1]
                    new_path = os.path.join(new_dir, f"{new_full_name}_{i}{ext}")
                    if old_path != new_path:
                        os.rename(old_path, new_path)
        
        # Cập nhật student trong database
        student.student_id = new_student_id
        student.full_name = new_full_name
        student.class_name = new_class_name
        student.email = new_email
        student.save()
        
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
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_recognize_face(request):
    """API nhận diện khuôn mặt từ ảnh base64"""
    try:
        data = json.loads(request.body)
        image_base64 = data.get('image')
        
        if not image_base64:
            return JsonResponse({
                'success': False,
                'error': 'Missing image'
            }, status=400)
        
        # Xóa header base64 nếu có
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]
        
        img_data = base64.b64decode(image_base64)
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return JsonResponse({
                'success': False,
                'error': 'Invalid image data'
            }, status=400)
        
        # Nhận diện khuôn mặt
        results = fr.recognize_frame(frame)
        
        recognized = []
        for name, score, bbox in results:
            if name != "Unknown":
                recognized.append({
                    'name': name,
                    'confidence': round(score * 100, 1),
                    'bbox': bbox.tolist() if hasattr(bbox, 'tolist') else bbox
                })
                
                # Tự động ghi nhận điểm danh
                try:
                    student = Student.objects.get(full_name=name)
                    current_time = timezone.now()
                    AttendanceRecord.objects.update_or_create(
                        student=student,
                        date=current_time.date(),
                        defaults={
                            'time_in': current_time,
                            'status': 'present',
                            'confidence': score
                        }
                    )
                except Student.DoesNotExist:
                    pass
        
        return JsonResponse({
            'success': True,
            'data': {
                'faces_detected': len(results),
                'recognized': recognized
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
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
def api_sessions_today(request):
    """API lấy các buổi điểm danh hôm nay"""
    today = timezone.now().date()
    sessions = AttendanceSession.objects.filter(date=today).select_related('schedule__subject', 'schedule__classroom')
    
    data = [{
        'id': s.id,
        'subject': s.schedule.subject.name,
        'classroom': s.schedule.classroom.name,
        'date': str(s.date),
        'status': s.status,
        'status_display': s.get_status_display(),
        'present_count': s.get_present_count(),
        'total_students': s.get_total_students(),
        'start_time': s.start_time.strftime('%H:%M:%S') if s.start_time else None,
    } for s in sessions]
    
    return JsonResponse({'success': True, 'data': data})


@require_http_methods(["GET"])
def api_session_attendance(request, session_id):
    """API lấy danh sách điểm danh của 1 buổi"""
    try:
        session = AttendanceSession.objects.get(id=session_id)
        records = session.session_records.select_related('student')
        
        data = [{
            'student_id': r.student.student_id,
            'student_name': r.student.full_name,
            'class_name': r.student.class_name,
            'time_in': r.time_in.strftime('%H:%M:%S') if r.time_in else None,
            'status': r.status,
            'confidence': round(r.confidence * 100, 1) if r.confidence else 0,
        } for r in records]
        
        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'subject': session.schedule.subject.name,
                'classroom': session.schedule.classroom.name,
                'date': str(session.date),
                'status': session.status,
            },
            'data': data
        })
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Session not found'}, status=404)


@csrf_exempt
@require_http_methods(["POST"])
def api_record_session_attendance(request):
    """API ghi nhận điểm danh cho 1 buổi học"""
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        student_name = data.get('student_name')
        confidence = data.get('confidence', 0)
        
        if not session_id or not student_name:
            return JsonResponse({
                'success': False,
                'error': 'Missing session_id or student_name'
            }, status=400)
        
        session = AttendanceSession.objects.get(id=session_id)
        student = Student.objects.get(full_name=student_name)
        
        current_time = timezone.now()
        
        # Tạo hoặc cập nhật bản ghi điểm danh
        record, created = AttendanceRecord.objects.update_or_create(
            session=session,
            student=student,
            date=current_time.date(),
            defaults={
                'time_in': current_time.time(),
                'status': 'present',
                'confidence': confidence,
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{student.full_name} đã điểm danh thành công',
            'data': {
                'student_name': student.full_name,
                'student_id': student.student_id,
                'class_name': student.class_name,
                'time_in': current_time.strftime('%H:%M:%S'),
                'date': str(current_time.date()),
                'session_id': session.id,
                'subject': session.schedule.subject.name,
                'created': created
            }
        })
        
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Session not found'}, status=404)
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
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
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.now().date()
        
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
        
        return JsonResponse({
            'success': True,
            'message': 'Đã tạo buổi điểm danh',
            'data': {
                'session_id': session.id,
                'subject': schedule.subject.name,
                'classroom': schedule.classroom.name,
                'date': str(date),
                'created': created
            }
        })
        
    except Schedule.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Schedule not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

