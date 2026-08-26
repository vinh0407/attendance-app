# Máy điểm danh — Face Attendance Kiosk

Kiosk portrait 4:6 camera-first, dùng camera thật của trình duyệt và gọi API Django đang có sẵn trong `django_app`.

Màu xanh trong UI là `UI BLUE — PROVISIONAL`. Logo UTH được lấy từ `assets/uth-logo.png` do người dùng cung cấp.

## Chạy

1. Khởi động Django từ `C:\VisualStudio\App điểm danh\django_app` (`python manage.py runserver`).
2. Mở kiosk tại `http://127.0.0.1:8000/kiosk/?device_id=KIOSK-A203`. Kiosk đã được Django phục vụ cùng origin; không mở `index.html` bằng `file://`, vì trình duyệt sẽ chặn camera và API.
3. Tạo/mở một `AttendanceSession` ở trạng thái `active` trong Management App. Kiosk tự tải buổi active đầu tiên trong `/api/sessions/today/`.
4. Cấp quyền camera khi được hỏi.

Có thể đặt mã kiosk mà không sửa source bằng query string, ví dụ `?device_id=KIOSK-IT01-01` (giá trị này cũng được lưu trong giao diện hiện tại).

## API đã dùng

- `GET /api/sessions/today/` — lấy buổi học thực tế trong ngày.
- `POST /api/recognize-face/` — gửi frame camera cùng `session_id` (mã `SES-...`) và `device_id`; Django/InsightFace là nguồn nhận diện và ghi điểm danh.

Response trả về cùng một attendance event cho kiosk, Management App và CSV: `attendance_id`, `late_minutes`, `attendance_code`, `attendance_label`, `attendance_periods`, `method` và `device_id`.

## Nguồn dữ liệu dùng chung

Kiosk, Management và Student Portal không có database riêng. Cả ba chạy cùng
origin Django và đọc/ghi `django_app/db.sqlite3` thông qua API. Kiosk chỉ gửi
ảnh + `session_id` + `device_id`; Django nhận diện, phân loại thời gian và tạo
một `AttendanceRecord`. Management, Portal và CSV export đọc lại chính bản ghi
đó.

CSV là đường backup/import, không phải realtime database. Đặt CSV vào:
`APP/Máy điểm danh/inbox/`, sau đó chạy:

```powershell
cd "C:\VisualStudio\App điểm danh\django_app"
..\venv\Scripts\python.exe manage.py import_attendance_csv --archive
```

File hợp lệ được chuyển vào `processed/`, file có dòng lỗi vào `failed/`.

## Attendance timing

Timing is calculated on the server from the session's scheduled period start:

- At or before the scheduled start: `PRESENT` / `ON TIME`.
- 1–15 minutes late: `LATE — LEVEL 1`.
- 16–59 minutes late: `LATE — 1 PERIOD`.
- 60–120 minutes late: `ABSENT — 2 PERIODS`.
- More than 120 minutes late: `ABSENT`.

The status is stored in `AttendanceRecord.status`; the detailed label is stored in the existing `notes` field. No new attendance record is created when the student is scanned again in the same session.

Không có student, attendance, confidence hay trạng thái online giả trong UI. Khi chưa có buổi active, kiosk khóa quét và hiển thị lý do.
