# UTH Face Attendance Kiosk

This directory contains the browser-based Attendance Kiosk. Django serves the Kiosk on the same origin as the attendance APIs.

The canonical project documentation is available in the repository root at `README.md`.

## Operation

1. Start Django from the repository root.
2. Open `http://127.0.0.1:8000/kiosk/` on the computer connected to the camera.
3. Ensure that an active attendance session exists for the current day.
4. Grant camera permission when the browser requests it.
5. Keep one face inside the guide during each scan.

The Kiosk selects the first active session returned by `/api/sessions/today/`. A specific session and device can be selected with query parameters:

```text
http://127.0.0.1:8000/kiosk/?session_id=5&device_id=KIOSK-A203
```

The `session_id` query parameter currently uses the numeric Django session ID for the roster request. Attendance responses also contain the stable external identifier beginning with `SES-`.

## API Integration

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/sessions/today/` | Load active sessions for the current date |
| `GET` | `/api/session/<id>/roster/` | Load the expected class roster and attendance state |
| `POST` | `/api/recognize-face/` | Submit a camera frame and record canonical attendance |

Requests include the `X-Kiosk-Key` header. The recognition request body contains:

```json
{
  "image": "data:image/jpeg;base64,...",
  "session_id": "SES-20260826-CV101-A203",
  "device_id": "KIOSK-A203"
}
```

The server performs recognition, class-membership validation, time classification, duplicate prevention, database persistence, and CSV archival. The Kiosk only displays the returned result.

## Camera Security

Modern browsers allow camera access on loopback addresses such as `127.0.0.1`. Camera access from another device through a private IP address normally requires HTTPS. Do not open `index.html` through `file://` because browser security rules will block the camera and same-origin API behavior.

## Data Ownership

The Kiosk does not maintain a separate attendance database. Django is the source of truth. The `inbox` directory is available only for optional CSV backup imports.
