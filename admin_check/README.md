# UTH Attendance Backend and Management Application

This directory contains the Django backend, staff Management Application, shared data model, attendance services, import commands, and API endpoints for the UTH Attendance System.

The canonical project documentation is available in the repository root at `README.md`.

## Responsibilities

- Staff authentication and management pages.
- Student, class, subject, schedule, session, attendance, grade, and camera models.
- Face registration and InsightFace inference.
- Canonical attendance timing and duplicate prevention.
- Wrong-class validation.
- Automatic attendance CSV archival.
- Session finalization and absent-record creation.
- Student-scoped Portal APIs.
- CSV import and export.

## Development Commands

Run these commands from the repository root after activating the virtual environment.

```powershell
$env:DJANGO_DEBUG = "1"
python .\admin_check\manage.py migrate
python .\admin_check\manage.py createsuperuser
python .\admin_check\manage.py runserver 0.0.0.0:8000
```

Run verification with:

```powershell
python .\admin_check\manage.py check
python .\admin_check\manage.py test portal
```

## Important Paths

| Path | Purpose |
| --- | --- |
| `attendance_system/settings.py` | Django settings and environment-variable integration |
| `attendance_system/urls.py` | Root URL configuration |
| `portal/models.py` | Shared database schema |
| `portal/views.py` | Management, Kiosk, Student Portal, and API views |
| `portal/attendance_service.py` | Canonical attendance rules and event persistence |
| `portal/attendance_archive.py` | Automatic date-and-subject CSV archive |
| `portal/attendance_import.py` | CSV validation and import |
| `portal/face_recognition.py` | InsightFace model, embedding storage, registration, and recognition |
| `portal/management/commands` | Roster, grade, attendance, and face utilities |

## Data Boundaries

The Django database, media directory, student data, attendance history, face embeddings, and environment files are excluded from Git. Do not add real student or biometric data to source control.
