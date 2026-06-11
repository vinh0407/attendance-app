# OpenCV AI Attendance System - Django

Hệ thống điểm danh thông minh sử dụng nhận diện khuôn mặt với OpenCV và Django.

## Cấu trúc Project

```
attendance_system/
├── manage.py                    # Django management script
├── requirements.txt             # Python dependencies
├── db.sqlite3                   # SQLite database (auto-generated)
│
├── attendance_system/           # Project configuration
│   ├── __init__.py
│   ├── settings.py              # Django settings
│   ├── urls.py                  # Main URL configuration
│   ├── asgi.py
│   └── wsgi.py
│
├── portal/                      # Main application
│   ├── __init__.py
│   ├── admin.py                 # Admin configuration
│   ├── apps.py
│   ├── models.py                # Database models
│   ├── views.py                 # Views & API endpoints
│   └── urls.py                  # App URLs
│
├── templates/                   # HTML templates
│   ├── base.html                # Base template
│   └── portal/
│       ├── home.html            # Main portal page
│       ├── admin_dashboard.html # Admin dashboard
│       ├── register.html        # Face registration page
│       └── scan_placeholder.html # Placeholder cho plugin OpenCV
│
└── static/                      # Static files
    ├── css/
    │   └── styles.css           # Custom styles
    └── js/
        └── main.js              # Main JavaScript
```

## Cài đặt & Chạy

### 1. Tạo Virtual Environment
```bash
cd attendance_system
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc: venv\Scripts\activate  # Windows
```

### 2. Cài đặt Dependencies
```bash
pip install -r requirements.txt
```

### 3. Migrate Database
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Tạo Superuser (Admin)
```bash
python manage.py createsuperuser
```

### 5. Chạy Server
```bash
python manage.py runserver
```

Truy cập: http://127.0.0.1:8000/

## URLs

| URL | Mô tả |
|-----|-------|
| `/` | Trang chủ Portal |
| `/admin-dashboard/` | Admin Dashboard |
| `/register/` | Đăng ký khuôn mặt mới |
| `/scan/camera/` | **Placeholder - Plugin OpenCV** |
| `/admin/` | Django Admin |

## API Endpoints

### GET `/api/stats/`
Lấy thống kê hệ thống realtime.

**Response:**
```json
{
    "success": true,
    "data": {
        "total_students": 1248,
        "attendance_rate": 96.4,
        "active_cameras": 8,
        "avg_scan_time": 0.8,
        "last_sync": "14:30:00"
    }
}
```

### POST `/api/record-attendance/`
Ghi nhận điểm danh (dùng cho plugin OpenCV).

**Request:**
```json
{
    "student_id": "SV001",
    "confidence": 98.5,
    "camera_id": "CAM01"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Attendance recorded",
    "data": {
        "student_name": "Nguyen Van A",
        "student_id": "SV001",
        "time": "14:30:45",
        "status": "present",
        "created": true
    }
}
```

### GET `/api/students/`
Lấy danh sách sinh viên.

### GET `/api/attendance/today/`
Lấy danh sách điểm danh hôm nay.

## Tích hợp Plugin OpenCV

### Cách 1: Thay đổi view `scan_camera`

Chỉnh sửa file `portal/views.py`:

```python
def scan_camera(request):
    # Thêm logic OpenCV của anh vào đây
    # ...
    return render(request, 'portal/your_opencv_template.html', context)
```

### Cách 2: Tạo app riêng cho OpenCV

```bash
python manage.py startapp opencv_plugin
```

Sau đó thêm vào `INSTALLED_APPS` trong `settings.py`.

### Cách 3: Redirect tới URL khác

Trong `settings.py`, thay đổi:
```python
OPENCV_PLUGIN_URL = 'http://localhost:5000/camera'  # URL tới plugin riêng
```

## Cấu hình

Các URL có thể cấu hình trong `attendance_system/settings.py`:

```python
# OpenCV Plugin Configuration
OPENCV_PLUGIN_URL = '/scan/camera/'      # URL plugin OpenCV
ADMIN_DASHBOARD_URL = '/admin-dashboard/'
REGISTER_FACE_URL = '/register/'
```

## Models

### Student
- `student_id`: Mã sinh viên (unique)
- `full_name`: Họ tên
- `email`: Email
- `class_name`: Lớp
- `face_encoding`: Face encoding data (binary)
- `face_image`: Ảnh khuôn mặt
- `is_registered`: Đã đăng ký khuôn mặt chưa

### AttendanceRecord
- `student`: FK tới Student
- `date`: Ngày điểm danh
- `time_in`: Giờ vào
- `time_out`: Giờ ra
- `status`: present/late/absent
- `confidence`: Độ tin cậy nhận diện
- `camera_id`: ID camera

### Camera
- `camera_id`: ID camera
- `name`: Tên
- `location`: Vị trí
- `ip_address`: Địa chỉ IP
- `status`: active/inactive/maintenance

## Development

### Thêm dữ liệu mẫu
```bash
python manage.py shell
```

```python
from portal.models import Student, Camera

# Thêm sinh viên
Student.objects.create(
    student_id='SV001',
    full_name='Nguyen Van A',
    class_name='CS101'
)

# Thêm camera
Camera.objects.create(
    camera_id='CAM01',
    name='Camera Lớp 101',
    location='Phòng 101',
    status='active'
)
```

## License
MIT License
# nhan-dien-khuonmat-website
