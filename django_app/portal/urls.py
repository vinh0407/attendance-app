from django.urls import path
from . import views
from . import extra_views

app_name = 'portal'

urlpatterns = [
    # Main pages
    path('', views.home, name='home'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('register/', views.register_face, name='register'),

    # Scan camera voi face recognition
    path('scan/camera/', views.scan_camera, name='scan_camera'),
    path('video_feed/', views.video_feed, name='video_feed'),

    # Thoi khoa bieu va Diem danh theo buoi
    path('schedule/', views.schedule_view, name='schedule'),
    path('session/start/<int:schedule_id>/', views.start_attendance_session, name='start_session'),
    path('session/<int:session_id>/', views.attendance_session, name='attendance_session'),
    path('session/<int:session_id>/end/', views.end_attendance_session, name='end_session'),
    path('session/<int:session_id>/video_feed/', views.video_feed_session, name='video_feed_session'),

    # API Endpoints
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/record-attendance/', views.api_record_attendance, name='api_record_attendance'),
    path('api/students/', views.api_students, name='api_students'),
    path('api/attendance/today/', views.api_attendance_today, name='api_attendance_today'),

    # Face Recognition APIs
    path('api/register-face/', views.api_register_face, name='api_register_face'),
    path('api/recognize-face/', views.api_recognize_face, name='api_recognize_face'),
    path('api/registered-faces/', views.api_registered_faces, name='api_registered_faces'),

    # Schedule & Session APIs
    path('api/schedules/', views.api_schedules, name='api_schedules'),
    path('api/sessions/today/', views.api_sessions_today, name='api_sessions_today'),
    path('api/session/<int:session_id>/attendance/', views.api_session_attendance, name='api_session_attendance'),
    path('api/session/record/', views.api_record_session_attendance, name='api_record_session_attendance'),
    path('api/session/create/', views.api_create_session, name='api_create_session'),

    # Admin APIs
    path('api/delete-student/<int:student_id>/', views.api_delete_student, name='api_delete_student'),
    path('api/update-student/<int:student_id>/', views.api_update_student, name='api_update_student'),

    # === TEST & SYNC Utilities ===
    # Dong bo face_database.pkl -> Django Student DB
    path('api/sync-faces/', extra_views.api_sync_faces, name='api_sync_faces'),
    # Test nhan dien anh va ghi diem danh (POST multipart voi field 'image')
    path('api/test-image/', extra_views.api_test_image, name='api_test_image'),
]
