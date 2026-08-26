# UTH Attendance System

UTH Attendance System is a unified face-recognition attendance platform designed for classroom use on a local university network. The repository contains an attendance kiosk, a staff management application, and a student portal. All three surfaces use the same Django backend, database, attendance rules, and CSV archive.

All project documentation is consolidated in this file so that setup, architecture, operation, testing, security, and deployment guidance remain consistent.

The current implementation is suitable for development, demonstrations, and controlled local-network testing. It is not yet a production deployment package. Review the security and deployment sections before using real student or biometric data.

## System Overview

The platform is divided into three user-facing components.

| Component | Primary users | Responsibilities | Location |
| --- | --- | --- | --- |
| Attendance Kiosk | Students and classroom operators | Loads an active class session, opens the camera, recognizes a face, verifies class membership, and submits attendance | `APP/Máy điểm danh` |
| Management Application | Administrators and teaching staff | Manages students, face registration, classes, subjects, schedules, attendance sessions, postponements, finalization, and CSV exports | `admin_check` |
| Student Portal | Students | Displays the authenticated student's schedule, grades, attendance history, subject totals, and exam eligibility | `APP/Portal` |

The Django application is the source of truth. The Kiosk and Student Portal do not maintain separate databases. Attendance events are written once to Django and are then read by the Management Application, Student Portal, session exports, and automatic CSV archives.

## Main Capabilities

### Attendance Kiosk

- Uses the browser camera through `getUserMedia`.
- Loads today's active attendance sessions from Django.
- Sends camera frames to the InsightFace recognition endpoint.
- Prevents attendance when a recognized student is not enrolled in the selected class.
- Prevents duplicate records for the same student and session.
- Displays the canonical attendance status returned by the server.
- Supports a configurable `device_id` query parameter for kiosk identification.

### Management Application

- Staff-only Django authentication.
- Student roster management.
- Face registration inside the Admin Dashboard.
- Face engine health and active inference-provider reporting.
- Class and subject creation.
- Subject assignment and weekly schedule creation.
- Automatic creation of today's scheduled attendance sessions.
- Session postponement and optional rescheduling.
- Session finalization with automatic absent records for unscanned students.
- Session-level and system-wide CSV exports.
- CSV import for rosters, grades, attendance history, and kiosk backup files.

### Student Portal

- Student sign-in using an administrator-registered Student ID and class value.
- Student-scoped dashboard response with no access to other students' records.
- Today's schedule and complete weekly schedule.
- Attendance history and summary totals.
- Grade ledger by subject, semester, and assessment type.
- Per-subject late and absent-period totals.
- Exam prohibition when recorded absent periods for a subject exceed three.
- Responsive desktop, tablet, and mobile navigation.

## Architecture

| Layer | Technology | Purpose |
| --- | --- | --- |
| Web backend | Django | Routing, authentication, business rules, APIs, data persistence, and exports |
| Database | SQLite | Shared development and demonstration database |
| Face recognition | InsightFace 1.0.1 | Face detection and embedding comparison |
| Inference runtime | ONNX Runtime | CUDA, DirectML, or CPU execution |
| Image processing | OpenCV and NumPy | Camera-frame decoding and preprocessing |
| Management frontend | Django templates, CSS, JavaScript | Staff workflows |
| Kiosk frontend | HTML, CSS, JavaScript | Camera and attendance workflow |
| Student frontend | HTML, CSS, JavaScript | Student academic dashboard |

The backend selects an inference provider in this order when available:

1. `CUDAExecutionProvider`
2. `DmlExecutionProvider`
3. `CPUExecutionProvider`

The Management Application exposes the active provider in the face-registration workspace so the deployment can be verified without inspecting server logs.

## Attendance Workflow

1. An administrator imports or creates student records.
2. The administrator creates a class and assigns students to it.
3. The administrator creates a subject and assigns it to the class through a weekly schedule.
4. The student's face is registered from the Admin Dashboard.
5. Opening the schedule page ensures that today's scheduled sessions exist and are active.
6. The Kiosk loads a session and sends a camera frame, session identifier, device identifier, and kiosk API key to Django.
7. Django recognizes the face and checks whether the student belongs to the session's class.
8. Django calculates attendance from the scheduled period and the server check-in time.
9. One canonical `AttendanceRecord` is committed to the database.
10. After the database commit, the same record is appended to the date-and-subject CSV archive.
11. When staff finalize the session, Django creates `ABSENT` records for every roster member without an attendance record.
12. The Management Application and Student Portal read the resulting records from the shared database.

## Attendance Classification

Attendance timing is calculated only in `admin_check/portal/attendance_service.py`. Frontends display the result and do not recalculate it.

| Arrival time | Database status | Attendance code | Counted periods |
| --- | --- | --- | --- |
| At or before the scheduled start | `present` | `ON_TIME` | 0 |
| 1 to 15 minutes late | `late` | `LATE_LEVEL_1` | 0 |
| 16 to 59 minutes late | `late` | `LATE_ONE_PERIOD` | 1 |
| 60 to 120 minutes late | `absent` | `ABSENT_TWO_PERIODS` | 2 |
| More than 120 minutes late | `absent` | `ABSENT` | Not fixed |
| Not scanned when the session is finalized | `absent` | `ABSENT` | Full scheduled session length |

Minute boundaries are derived from elapsed seconds. For example, an arrival at 15 minutes and 59 seconds is still classified as 15 minutes late; an arrival at 16 minutes is classified as one period late.

## Data Model

The core Django models are defined in `admin_check/portal/models.py`.

| Model | Purpose |
| --- | --- |
| `Student` | Student identity, class label, email, face-registration state, and optional Django user link |
| `Subject` | Subject code, name, teacher, and credits |
| `ClassRoom` | Class identifier, name, department, and student membership |
| `Schedule` | Weekly subject, class, room, day, and period assignment |
| `AttendanceSession` | A dated occurrence of a schedule with scheduled, active, completed, cancelled, or postponed state |
| `AttendanceRecord` | One student's canonical result for one session |
| `Grade` | A student's assessment score for a subject and semester |
| `Camera` | Registered camera or kiosk metadata |
| `SystemStats` | Optional daily aggregate statistics |

The database enforces one attendance record per student and attendance session.

## Data Storage

### Shared database

The development database is stored at:

```text
admin_check/db.sqlite3
```

This file is excluded from Git because it can contain private student and attendance information.

### Face profiles

Face registration stores each student's files under:

```text
APP/Dữ liệu/Sinh viên trường/<Full Name>_<Class>/
```

A profile directory contains:

```text
face.png
face_02.png
student.json
```

Face embeddings are stored in the local `face_database.pkl` file. Student images, metadata, embeddings, and the database file are excluded from Git.

### Attendance history

Every committed attendance event is archived automatically under:

```text
APP/Dữ liệu/Lịch sử điểm danh/DD_MM_YYYY/<Subject Name>/attendance.csv
```

The database remains authoritative. CSV files are durable integration and reporting artifacts, not an independent real-time database.

### Kiosk import inbox

Optional backup CSV files can be placed in:

```text
APP/Máy điểm danh/inbox
```

When archival import is enabled, accepted files are moved to `processed` and files containing rejected rows are moved to `failed`.

## Attendance CSV Contract

The automatic history archive uses the following columns:

```csv
attendance_id,session_id,student_id,student_name,subject_id,subject_name,date,scheduled_time,check_in_time,late_minutes,status,attendance_periods,method,device_id
```

Example:

```csv
ATT-20260826-0001,SES-20260826-CV101-A203,2251120064,Nguyen Van A,CV101,Computer Vision,2026-08-26,07:30:00,07:29:15,0,ON_TIME,0,FACIAL_RECOGNITION,KIOSK-A203
```

Attendance imports accept stable external session identifiers and legacy numeric database identifiers. Imported rows are validated through the same attendance service used by live kiosk events.

## Repository Structure

```text
attendance-app/
|-- admin_check/
|   |-- attendance_system/        Django project settings and root URLs
|   |-- portal/                   Models, APIs, services, imports, and tests
|   |-- templates/                Management Application templates
|   |-- static/                   Management Application assets
|   |-- manage.py                 Django command entry point
|   `-- requirements.txt          Python dependencies
|-- APP/
|   |-- Máy điểm danh/            Attendance Kiosk frontend
|   |-- Portal/                   Student Portal frontend
|   `-- Dữ liệu/                  Local roster, grade, face, and attendance data
|-- .gitignore                    Private-data and runtime exclusions
`-- README.md                     Complete project documentation
```

## Requirements

- Windows 10 or Windows 11 for the current tested setup.
- Python 3.10 or newer. Python 3.12 is used by the current development environment.
- A modern Chromium-based browser with camera support.
- A webcam for live kiosk testing.
- Sufficient local disk space for Python packages, ONNX Runtime, and the selected InsightFace model.
- A trusted HTTPS endpoint when a kiosk camera is opened from another device on the network.

An NVIDIA GPU is optional. The application falls back to DirectML or CPU when a usable CUDA provider is unavailable.

## Quick Start on Windows

Run the following commands from the repository root in PowerShell.

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r .\admin_check\requirements.txt
```

The default requirements install the CPU version of ONNX Runtime. See the inference-backend section before replacing it with a GPU runtime.

### 3. Configure the development process

```powershell
$env:DJANGO_DEBUG = "1"
$env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost"
```

For a LAN demonstration, append the server computer's private IP address:

```powershell
$env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost,192.168.1.97"
```

`admin_check/.env.example` documents the supported variables. The current settings module reads process environment variables directly; it does not automatically load a `.env` file.

### 4. Apply database migrations

```powershell
python .\admin_check\manage.py migrate
```

### 5. Create a staff account

```powershell
python .\admin_check\manage.py createsuperuser
```

### 6. Start the server

```powershell
python .\admin_check\manage.py runserver 0.0.0.0:8000
```

### 7. Open the applications

| Application | Local URL |
| --- | --- |
| Management Application | `http://127.0.0.1:8000/admin-dashboard/` |
| Weekly Schedule | `http://127.0.0.1:8000/schedule/` |
| Attendance Kiosk | `http://127.0.0.1:8000/kiosk/` |
| Student Portal | `http://127.0.0.1:8000/student-portal/` |
| Django Administration | `http://127.0.0.1:8000/admin/` |

## Initial Demonstration Setup

1. Sign in to Django Administration or the Management Application with a staff account.
2. Import or create students.
3. Create a class and attach students by Student ID.
4. Create a subject.
5. Assign the subject to the class, day, room, and teaching periods.
6. Register each student's face from the face-registration section of the Management Application.
7. Open `/schedule/` on the scheduled day so today's sessions are created and activated.
8. Open the Kiosk. It selects the first active session when no session is supplied.
9. To target a specific session, use its numeric Django session ID:

```text
http://127.0.0.1:8000/kiosk/?session_id=5&device_id=KIOSK-A203
```

10. Grant camera permission and scan a registered student.
11. Finalize the session in the Management Application to create absent records for students who were not scanned.
12. Sign in to the Student Portal using the student's registered Student ID and class ID or class name.

## Import Commands

All commands below are run from the repository root after activating the virtual environment.

### Student roster

Supported formats are CSV, TSV, JSON, and JSONL.

```powershell
python .\admin_check\manage.py import_students --dry-run
python .\admin_check\manage.py import_students
```

Required fields are `student_id` and `full_name`. Optional fields are `class_name` and `email`. Common Vietnamese and English header aliases are accepted.

To import a specific file or directory:

```powershell
python .\admin_check\manage.py import_students "C:\path\to\students.csv"
```

### Grades

```powershell
python .\admin_check\manage.py import_grades --dry-run
python .\admin_check\manage.py import_grades
```

The canonical grade columns are:

```csv
student_id,subject_id,semester,assessment_type,score
```

Students and subjects must already exist before their grades can be imported.

### Attendance history

```powershell
python .\admin_check\manage.py import_attendance_history
```

The command scans `APP/Dữ liệu/Lịch sử điểm danh` recursively and imports every CSV file it finds.

### Kiosk backup CSV

```powershell
python .\admin_check\manage.py import_attendance_csv --archive
```

To import a specific file or directory:

```powershell
python .\admin_check\manage.py import_attendance_csv "C:\path\to\attendance.csv" --archive
```

## Inference Backend Configuration

### CPU

The default requirements install `onnxruntime`, which is the most portable configuration.

```powershell
python -m pip install onnxruntime
```

### NVIDIA CUDA

Install a version of ONNX Runtime GPU that is compatible with the machine's NVIDIA driver and CUDA libraries.

```powershell
python -m pip uninstall -y onnxruntime onnxruntime-directml
python -m pip install onnxruntime-gpu
```

Do not install CPU, DirectML, and GPU runtime packages together unless their compatibility has been verified. A visible CUDA provider is used only when its native provider library can load successfully.

### Windows DirectML

DirectML is the Windows fallback when CUDA is unavailable but supported graphics hardware is present.

```powershell
python -m pip uninstall -y onnxruntime onnxruntime-gpu
python -m pip install onnxruntime-directml==1.24.4
```

Check the selected provider in the Management Application or through the staff-authenticated endpoint:

```text
GET /api/face-engine/status/
```

## API Summary

### Kiosk APIs

Kiosk requests require the `X-Kiosk-Key` header unless the caller already has an authenticated staff session.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/sessions/today/` | Return today's active sessions |
| `GET` | `/api/session/<id>/roster/` | Return the complete expected roster and current state |
| `POST` | `/api/recognize-face/` | Recognize a frame, verify enrollment, and record attendance |
| `POST` | `/api/session/record/` | Record a recognized student through the canonical attendance service |

Kiosk traffic is limited to 120 requests per IP address and minute bucket.

### Staff APIs

These endpoints require an authenticated Django staff session.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/face-engine/status/` | Return face-engine dependency and provider status |
| `POST` | `/api/register-face/` | Register up to five face images for a student |
| `GET` | `/api/registered-faces/` | List registered face identities |
| `POST` | `/api/classes/create/` | Create or update a class |
| `POST` | `/api/subjects/create/` | Create or update a subject |
| `POST` | `/api/schedules/create/` | Assign a subject and teaching periods to a class |
| `POST` | `/api/session/create/` | Create or activate a dated attendance session |
| `POST` | `/api/session/<id>/postpone/` | Postpone and optionally reschedule a session |
| `POST` | `/api/session/<id>/finalize/` | Complete a session and create missing absent records |
| `GET` | `/api/session/<id>/export.csv` | Export one session roster and attendance result |
| `GET` | `/api/export/all.csv` | Export students, classes, schedules, sessions, attendance, and grades |

### Student APIs

Student endpoints use an isolated, student-scoped Django session.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/student/login/` | Start a Portal session with Student ID and class |
| `POST` | `/api/student/logout/` | End the Portal identity session |
| `GET` | `/api/student/me/dashboard/` | Return the optimized complete dashboard payload |
| `GET` | `/api/student/me/profile/` | Return the current student's profile |
| `GET` | `/api/student/me/schedule/today/` | Return today's schedule |
| `GET` | `/api/student/me/attendance/` | Return attendance history |
| `GET` | `/api/student/me/attendance/summary/` | Return attendance totals |
| `GET` | `/api/student/me/grades/` | Return the grade ledger |
| `GET` | `/api/student/me/subjects/summary/` | Return per-subject attendance and exam eligibility |

## Environment Variables

| Variable | Purpose | Development default |
| --- | --- | --- |
| `UTH_SECRET_KEY` | Django cryptographic signing key | Insecure development value |
| `UTH_KIOSK_API_KEY` | Shared key accepted from kiosk requests | Insecure development value |
| `DJANGO_DEBUG` | Enables Django debug and development static serving when set to `1` | `0` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names and IP addresses | `127.0.0.1,localhost` |
| `DJANGO_SECURE_SSL_REDIRECT` | Redirects HTTP to HTTPS when set to `1` and debug is disabled | `0` |
| `DJANGO_SECURE_HSTS_SECONDS` | HSTS duration for a non-debug deployment | `31536000` |
| `UTH_LOG_LEVEL` | Log level for the `portal` logger | `INFO` |

The current static kiosk uses the development key unless `window.KIOSK_API_KEY` is injected before `kiosk.js` loads. A production deployment must replace this mechanism so kiosk credentials are provisioned per device and are not committed to source control.

## Local Network and Camera Access

The server can listen on the LAN with `0.0.0.0:8000`, but browser camera access has an additional security requirement.

- `http://127.0.0.1:8000/kiosk/` can use the camera on the server computer because browsers treat loopback addresses as secure contexts.
- `http://<private-ip>:8000/kiosk/` can be opened from another device, but most browsers will block camera access over plain HTTP.
- Use HTTPS through a trusted reverse proxy or local development certificate when the kiosk runs on another computer, tablet, or phone.

The Management Application and Student Portal can be demonstrated over a private HTTP LAN, but HTTPS is still recommended whenever real student data is involved.

## Security and Privacy

The repository includes several protective controls:

- Staff mutations require an authenticated Django staff user.
- Student APIs return only the student identity stored in the current Portal session.
- Student sign-in is rate-limited to ten failed attempts per Student ID and IP combination over five minutes.
- Portal sessions expire after eight hours.
- Kiosk APIs require a shared key and apply request-rate limiting.
- Duplicate attendance is prevented by a database constraint.
- Uploaded face-registration requests are limited to five images.
- Kiosk image payload size is limited before decoding.
- Private databases, student folders, face images, attendance history, and kiosk inbox files are excluded from Git.

Current limitations that must be addressed before production use:

- Student ID plus class is an identity check, not password-based or institutional single sign-on authentication.
- SQLite is intended for a single demonstration server and limited concurrent writes.
- Face embeddings are stored in a local pickle file without encryption at rest.
- The development kiosk key is visible in static JavaScript.
- HTTPS termination, backup policy, retention policy, consent records, and administrator audit logging are not included.
- Session finalization is a staff action; there is no background scheduler that automatically closes every class.

Do not commit real student, grade, attendance, face-image, embedding, database, or secret files.

## Testing

Run the Django system check and Portal test suite from the repository root:

```powershell
python .\admin_check\manage.py check
python .\admin_check\manage.py test portal
```

The Portal suite currently covers:

- Attendance timing boundaries.
- Idempotent CSV attendance import.
- Uppercase kiosk attendance codes.
- Class creation and session postponement.
- Subject creation and schedule assignment.
- Complete system CSV export.
- Session finalization and automatic absent records.
- Student grade and subject-summary scoping.
- Student Portal sign-in, rejection, and session isolation.

Test face recognition without recording attendance:

```powershell
python .\admin_check\manage.py test_recognize --image "C:\path\to\face.png" --no-save
```

## Troubleshooting

### The camera does not open

- Use `127.0.0.1` when the kiosk and browser run on the same computer.
- Use HTTPS when opening the kiosk through a LAN IP address.
- Confirm that the browser has camera permission.
- Confirm that no other application is holding exclusive access to the camera.

### The Kiosk reports that no session is available

- Confirm that a schedule exists for the current weekday.
- Open `/schedule/` as a staff user to create and activate today's sessions.
- Confirm that the session is not completed, postponed, or cancelled.
- Supply a valid numeric session ID in the Kiosk URL when selecting a specific session.

### A face is recognized but attendance is rejected

- Confirm that the student belongs to the class assigned to the session.
- Confirm that the session status is `active`.
- Confirm that the Kiosk and server use the same kiosk API key.
- Inspect `/api/face-engine/status/` while signed in as staff.

### Face registration succeeds but recognition fails

- Register a clear, front-facing image with even lighting.
- Add several images with modest pose variation.
- Confirm that `face_database.pkl` contains the Student ID identity.
- Confirm that the registered profile folder contains `face.png` and `student.json`.
- Verify the active ONNX Runtime provider.

### PowerShell cannot display command help for Unicode paths

Set UTF-8 output for the current process before running the command:

```powershell
$env:PYTHONIOENCODING = "utf-8"
```

## Production Readiness Checklist

Before deploying beyond a controlled demonstration:

1. Replace all development secrets and kiosk keys.
2. Serve the application through HTTPS.
3. Move kiosk configuration out of committed static JavaScript.
4. Replace Student ID and class sign-in with institutional authentication.
5. Encrypt biometric data at rest and define access, consent, and retention controls.
6. Add a production database and connection configuration.
7. Add a production WSGI server and static-file strategy.
8. Add scheduled session finalization and operational monitoring.
9. Add database and biometric backup procedures.
10. Perform privacy, security, and load testing with non-production data.

## Git Data Policy

The `.gitignore` file excludes:

- Python virtual environments and caches.
- SQLite databases and collected static files.
- Environment and secret files.
- Face images and face embeddings.
- Student rosters and grade files.
- Attendance-history CSV files.
- Kiosk inbox, processed, and failed files.
- Local UI review captures.

Only `.gitkeep` files preserve the intended private-data directory structure in a fresh clone.

## Project License

No project-level open-source license has been declared. Third-party dependencies and vendored assets retain their respective licenses. The locally vendored Phosphor icon font used by the Student Portal includes its MIT license at `APP/Portal/assets/icons/phosphor/LICENSE.txt`.
