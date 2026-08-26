# UTH Attendance System

Three-part attendance platform for a school LAN:

1. **Attendance Kiosk** – automatic face recognition and real-time check-in.
2. **Admin** – students, face registration, classes, schedules, sessions and CSV exports.
3. **Student Portal** – schedule, grades, attendance history, subject statistics and exam eligibility.

All three clients use one Django API and database. Realtime attendance is written to the database and archived automatically as:

```text
APP/Dữ liệu/Lịch sử điểm danh/DD_MM_YYYY/<subject>/attendance.csv
```

Private biometric files, the local SQLite database and real school rosters are intentionally excluded from Git.

## Run the demo

```powershell
cd admin_check
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Open:

- Kiosk: `http://127.0.0.1:8000/kiosk/`
- Admin: `http://127.0.0.1:8000/admin-dashboard/`
- Student Portal: `http://127.0.0.1:8000/student-portal/`

For a LAN demo, replace `127.0.0.1` with the server computer's private IP.

## Import real data

- Student roster: put CSV/TSV/JSON files in `APP/Dữ liệu/Sinh viên trường`, then run `python manage.py import_students`.
- Grades: put a CSV with `student_id,subject_id,semester,assessment_type,score` in `APP/Dữ liệu/Admin`, then run `python manage.py import_grades`.
- Attendance history: put CSV files under `APP/Dữ liệu/Lịch sử điểm danh`, then run `python manage.py import_attendance_history`.

## Verify

```powershell
python manage.py test portal
```

The demo contains no fabricated student, biometric or attendance records.
