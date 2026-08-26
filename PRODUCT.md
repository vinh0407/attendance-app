# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing Django/Python application with a vanilla HTML/CSS/JavaScript kiosk surface.

## Users

Students standing at a fixed kiosk outside a classroom. Teaching staff and administrators operate the existing management app and attendance sessions.

## Product Purpose

The kiosk identifies a student through the existing InsightFace pipeline and records attendance for the active class session without requiring login, typing, or button presses.

## Positioning

One person, one face, one attendance record, with the server remaining the source of truth for recognition, session validity, timing status, and duplicate protection.

## Operating Context

The kiosk runs unattended at a classroom entrance on a portrait 4:6 display. Students look at the live camera, align their face, receive a clear confirmation, and leave. The management app creates and monitors class sessions.

## Capabilities and Constraints

- Existing camera, face detection, face recognition, student identification, and Django attendance APIs must remain intact.
- The kiosk uses the real browser camera and calls `/api/sessions/today/` and `/api/recognize-face/`.
- Attendance timing is computed from the scheduled period start; duplicate scans in one session must not create another record.
- UI copy is English.
- Primary device composition is portrait 4:6 with landscape fallback.
- No fake students, attendance, recognition results, confidence values, or online status may be introduced.

## Brand Commitments

- UTH / University of Transport Ho Chi Minh City.
- User-provided UTH logo asset: `APP/Máy điểm danh/assets/uth-logo.png`.
- White and UTH-blue visual direction; exact official brand color values remain unverified, so UI blue is provisional.

## Evidence on Hand

- Existing Python face recognition engine: `project.py` and `admin_check/portal/face_recognition.py`.
- Existing Django models and APIs: `admin_check/portal/models.py` and `admin_check/portal/views.py`.
- User-provided logo asset at `APP/Máy điểm danh/assets/uth-logo.png`.

## Product Principles

- Camera first: the next action must be obvious within seconds.
- Trust through clarity: show real session and attendance states without exposing model internals.
- Automatic by default: no unnecessary student interaction.
- Server-confirmed attendance: never claim success before backend confirmation.
- Calm institutional presence: readable, quiet, and appropriate for a university entrance.

## Accessibility & Inclusion

High contrast, large readable instruction text, semantic status messages, visible keyboard focus, status communication beyond color, and reduced-motion support are required.
