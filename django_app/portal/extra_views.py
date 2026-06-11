"""
Extra API views for testing and synchronization.
"""
import json
import base64
import os
import pickle
import cv2
import numpy as np

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings

from .models import Student, AttendanceRecord
from . import face_recognition as fr


@csrf_exempt
@require_http_methods(["POST"])
def api_test_image(request):
    """
    API test nhan dien khuon mat tu anh upload.
    POST /api/test-image/ voi multipart form-data field 'image'
    hoac JSON body {'image_base64': '...'}.
    Tu dong ghi diem danh neu nhan dien duoc.
    """
    try:
        frame = None

        # Uu tien file upload
        if request.FILES.get('image'):
            img_file = request.FILES['image']
            img_data = img_file.read()
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            try:
                data = json.loads(request.body)
            except Exception:
                data = {}
            img_b64 = data.get('image_base64') or data.get('image', '')
            if img_b64:
                if ',' in img_b64:
                    img_b64 = img_b64.split(',')[1]
                img_data = base64.b64decode(img_b64)
                nparr = np.frombuffer(img_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return JsonResponse({
                'success': False,
                'error': 'Khong doc duoc anh. Hay upload file anh (field ten: image).'
            }, status=400)

        # Nhan dien khuon mat
        results = fr.recognize_face(frame)
        recognized = []
        attendance_results = []

        for r in results:
            name = r['name']
            conf = r['confidence']
            recognized.append({
                'name': name,
                'confidence': round(conf, 1),
                'bbox': r['bbox']
            })

            if name != 'Unknown':
                try:
                    student = Student.objects.filter(full_name=name).first()
                    if student:
                        current_time = timezone.now()
                        record, created = AttendanceRecord.objects.update_or_create(
                            student=student,
                            date=current_time.date(),
                            session=None,
                            defaults={
                                'time_in': current_time.time(),
                                'status': 'present',
                                'confidence': conf / 100.0,
                            }
                        )
                        attendance_results.append({
                            'student_id': student.student_id,
                            'student_name': student.full_name,
                            'class_name': student.class_name,
                            'time': current_time.strftime('%H:%M:%S'),
                            'confidence': round(conf, 1),
                            'status': 'present',
                            'is_new': created,
                        })
                    else:
                        attendance_results.append({
                            'student_name': name,
                            'error': 'Chua co trong DB. Goi GET /api/sync-faces/ truoc!'
                        })
                except Exception as e:
                    attendance_results.append({'student_name': name, 'error': str(e)})

        return JsonResponse({
            'success': True,
            'faces_detected': len(results),
            'faces_recognized': len([r for r in results if r['name'] != 'Unknown']),
            'recognized': recognized,
            'attendance': attendance_results,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def api_sync_faces(request):
    """
    API dong bo face_database.pkl -> Django Student DB.
    GET /api/sync-faces/
    """
    try:
        # Duong dan: BASE_DIR = django_app/, cha no la thu muc goc project
        project_root = os.path.dirname(str(settings.BASE_DIR))
        db_file = os.path.join(project_root, 'face_database.pkl')

        if not os.path.exists(db_file):
            return JsonResponse({
                'success': False,
                'error': 'Khong tim thay face_database.pkl',
                'tried_path': db_file,
                'BASE_DIR': str(settings.BASE_DIR),
            }, status=404)

        with open(db_file, 'rb') as f:
            face_db = pickle.load(f)

        created_list = []
        updated_list = []

        # Tinh toan student_id tiep theo
        existing_ids = set(Student.objects.values_list('student_id', flat=True))
        sv_numbers = []
        for sid in existing_ids:
            try:
                sv_numbers.append(int(sid.replace('SV', '')))
            except Exception:
                pass
        next_num = max(sv_numbers) + 1 if sv_numbers else 1

        for name, embeddings in face_db.items():
            student = Student.objects.filter(full_name=name).first()
            if student:
                if not student.is_registered:
                    student.is_registered = True
                    student.save()
                updated_list.append({'name': name, 'student_id': student.student_id})
            else:
                new_id = f'SV{next_num:03d}'
                while Student.objects.filter(student_id=new_id).exists():
                    next_num += 1
                    new_id = f'SV{next_num:03d}'
                student = Student.objects.create(
                    student_id=new_id,
                    full_name=name,
                    class_name='CNTT01',
                    is_registered=True,
                )
                created_list.append({'name': name, 'student_id': new_id})
                next_num += 1

        return JsonResponse({
            'success': True,
            'message': f'Dong bo hoan tat: {len(created_list)} tao moi, {len(updated_list)} cap nhat',
            'created': created_list,
            'updated': updated_list,
            'total_students': Student.objects.count(),
            'face_db_count': len(face_db),
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
