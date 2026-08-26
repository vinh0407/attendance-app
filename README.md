# UTH Attendance System

![UTH Attendance](https://img.shields.io/badge/UTH-Attendance_System-1D4ED8?style=for-the-badge)
![Django](https://img.shields.io/badge/Django-4.2%2B-092E20?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![InsightFace](https://img.shields.io/badge/InsightFace-1.0.1-7C3AED?style=for-the-badge)
![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-1.18%2B-005CED?style=for-the-badge&logo=onnx&logoColor=white)

UTH Attendance System is a face-recognition attendance platform for classroom demonstrations and controlled local-network use. It combines an attendance kiosk, a staff management application, and a student portal on one Django backend.

## Applications

| Application | Purpose | Location |
| --- | --- | --- |
| Attendance Kiosk | Recognizes students, validates class membership, and records attendance | `APP/Máy điểm danh` |
| Management Application | Manages students, faces, classes, subjects, schedules, sessions, and exports | `admin_check` |
| Student Portal | Shows schedules, grades, attendance history, and exam eligibility | `APP/Portal` |

All applications use the same database and attendance rules. Django is the source of truth; CSV files are generated for reporting and archival use.

## Key Features

- Face registration from the staff dashboard.
- InsightFace recognition with ONNX Runtime.
- Class, subject, and weekly schedule management.
- Automatic attendance classification based on arrival time.
- Rejection when a recognized student belongs to another class.
- Session postponement and finalization.
- Automatic absent records for students who do not check in.
- Student login using the registered Student ID and class.
- Grades and attendance statistics by subject.
- Exam prohibition when absence exceeds three periods.
- CSV import, automatic archival, and full-system export.

## Attendance Rules

| Arrival | Result | Counted periods |
| --- | --- | --- |
| On time | `ON_TIME` | 0 |
| 1–15 minutes late | `LATE_LEVEL_1` | 0 |
| 16–59 minutes late | `LATE_ONE_PERIOD` | 1 |
| 60–120 minutes late | `ABSENT_TWO_PERIODS` | 2 |
| More than 120 minutes late | `ABSENT` | Full session |
| No check-in when finalized | `ABSENT` | Full session |

Attendance is calculated on the server in `admin_check/portal/attendance_service.py`.

## Data Flow

1. Staff create or import students, classes, subjects, and schedules.
2. Staff register each student's face from the Management Application.
3. The Kiosk loads an active session and submits a camera frame.
4. Django recognizes the student and validates class membership.
5. Django saves one attendance record and appends it to the history CSV.
6. Staff finalize the session to mark missing students as absent.
7. The Management Application and Student Portal display the same results.

## Data Storage

The development database is stored at:

```text
admin_check/db.sqlite3
```

Registered face data is stored under:

```text
APP/Dữ liệu/Sinh viên trường/<Full Name>_<Class>/
```

Attendance history is archived by date and subject:

```text
APP/Dữ liệu/Lịch sử điểm danh/DD_MM_YYYY/<Subject Name>/attendance.csv
```

The attendance CSV format is:

```csv
attendance_id,session_id,student_id,student_name,subject_id,subject_name,date,scheduled_time,check_in_time,late_minutes,status,attendance_periods,method,device_id
```

Private student, biometric, attendance, database, and secret files are excluded from Git.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- Chromium-based browser
- Webcam for kiosk testing
- ONNX Runtime

An NVIDIA GPU is optional. The application can use CUDA, DirectML, or CPU inference.

## Quick Start

Run these commands from the repository root in PowerShell:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\admin_check\requirements.txt
python .\admin_check\manage.py migrate
python .\admin_check\manage.py createsuperuser
python .\admin_check\manage.py runserver 0.0.0.0:8000
```

Open the applications:

| Application | URL |
| --- | --- |
| Management Application | `http://127.0.0.1:8000/admin-dashboard/` |
| Schedule | `http://127.0.0.1:8000/schedule/` |
| Attendance Kiosk | `http://127.0.0.1:8000/kiosk/` |
| Student Portal | `http://127.0.0.1:8000/student-portal/` |
| Django Administration | `http://127.0.0.1:8000/admin/` |

To open a specific Kiosk session:

```text
http://127.0.0.1:8000/kiosk/?session_id=5&device_id=KIOSK-A203
```

## Demo Setup

1. Sign in with a staff account.
2. Create or import students.
3. Create a class and assign students.
4. Create a subject and weekly schedule.
5. Register student faces from the Admin Dashboard.
6. Open the schedule page to activate today's sessions.
7. Open the Kiosk and allow camera access.
8. Finalize the session after class.
9. Sign in to the Student Portal with a Student ID and class.

## Data Import

```powershell
python .\admin_check\manage.py import_students --dry-run
python .\admin_check\manage.py import_students
python .\admin_check\manage.py import_grades
python .\admin_check\manage.py import_attendance_history
python .\admin_check\manage.py import_attendance_csv --archive
```

Student imports support CSV, TSV, JSON, and JSONL. Grades use:

```csv
student_id,subject_id,semester,assessment_type,score
```

## Local Network Camera Access

Browsers allow camera access on `127.0.0.1`. Accessing the Kiosk from another device through a private IP normally requires HTTPS. Add the server IP to `DJANGO_ALLOWED_HOSTS` when testing on a LAN.

## Testing

```powershell
python .\admin_check\manage.py check
python .\admin_check\manage.py test portal
```

Test one face image without recording attendance:

```powershell
python .\admin_check\manage.py test_recognize --image "C:\path\to\face.png" --no-save
```

## Production Notes

This repository is intended for development and demonstration. Before production use:

- Replace development secrets and kiosk keys.
- Deploy through HTTPS.
- Use institutional authentication for students.
- Move from SQLite to a production database.
- Encrypt biometric data and define retention policies.
- Add backups, monitoring, audit logs, and automated session finalization.

## Repository Structure

```text
attendance-app/
|-- admin_check/          Django backend and Management Application
|-- APP/
|   |-- Máy điểm danh/    Attendance Kiosk
|   |-- Portal/           Student Portal
|   `-- Dữ liệu/          Local application data
|-- .gitignore
`-- README.md
```

## Demo
<img width="1265" height="712" alt="desktop" src="https://github.com/user-attachments/assets/94e7806a-9c4d-4fda-9a81-83e6459af1e8" />
Dashboard Portal
