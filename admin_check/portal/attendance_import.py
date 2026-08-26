"""Validated CSV backup/import bridge for the central attendance database.

CSV is intentionally a secondary integration path. The normal realtime path is
Kiosk -> Django recognition API. Imported rows still go through the same
canonical timing service and the same ``session + student`` duplicate rule.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import os
import re
from dataclasses import dataclass, field

from .attendance_service import (
    calculate_attendance_status,
    get_session_scheduled_time,
    record_attendance_event,
    record_absence_event,
    resolve_session,
)
from .models import AttendanceRecord, Student


CSV_COLUMNS = (
    "attendance_id", "session_id", "student_id", "student_name", "class_id",
    "subject_id", "subject_name", "date", "scheduled_time", "check_in_time",
    "late_minutes", "status", "attendance_code", "attendance_label",
    "attendance_periods", "method", "device_id",
)
REQUIRED_COLUMNS = {"attendance_id", "session_id", "student_id", "date", "scheduled_time", "status"}
STATUS_VALUES = {"present", "late", "absent"}


@dataclass
class ImportResult:
    imported: int = 0
    duplicates: int = 0
    failed: list[dict] = field(default_factory=list)

    @property
    def ok(self):
        return not self.failed


def _normalise_row(row):
    return {
        str(key or "").strip().lower().lstrip("\ufeff"): (value or "").strip()
        for key, value in row.items()
    }


def _parse_date(value):
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("date must use YYYY-MM-DD")


def _parse_time(value, field_name):
    text = (value or "").strip()
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            return dt.datetime.strptime(text, pattern).time()
        except ValueError:
            pass
    raise ValueError(f"{field_name} must use HH:MM[:SS]")


def _validate_status(row, timing):
    supplied = (row.get("status") or "").strip().upper()
    code = (row.get("attendance_code") or "").strip().upper()
    expected_status = timing["status"].upper()
    expected_code = timing["attendance_code"].upper()
    if supplied and supplied not in {expected_status.upper(), expected_code}:
        raise ValueError(f"status does not match canonical timing ({expected_code})")
    if code and code != expected_code:
        raise ValueError(f"attendance_code does not match canonical timing ({expected_code})")


def import_rows(rows, *, source="csv"):
    """Import an iterable of CSV dictionaries and return an ImportResult."""
    result = ImportResult()
    for row_number, raw_row in enumerate(rows, start=2):
        row = _normalise_row(raw_row)
        try:
            missing = sorted(REQUIRED_COLUMNS - set(row))
            if missing:
                raise ValueError(f"missing columns: {', '.join(missing)}")
            if not all(row.get(column) for column in REQUIRED_COLUMNS):
                raise ValueError("required values cannot be blank")

            attendance_id = row["attendance_id"]
            if len(attendance_id) > 40 or not re.match(r"^ATT-[A-Za-z0-9-]+$", attendance_id):
                raise ValueError("invalid attendance_id")
            date = _parse_date(row["date"])
            scheduled_time = _parse_time(row["scheduled_time"], "scheduled_time")
            supplied_status = (row.get('status') or '').strip().upper()
            check_in_time = None if not row.get('check_in_time') else _parse_time(row["check_in_time"], "check_in_time")
            if check_in_time is None and supplied_status not in {'ABSENT', 'ABSENT_TWO_PERIODS'}:
                raise ValueError('check_in_time is required for a present or late record')
            session = resolve_session(row["session_id"])
            if session.date != date:
                raise ValueError("row date does not match session date")
            if get_session_scheduled_time(session) != scheduled_time:
                raise ValueError("scheduled_time does not match session schedule")

            student = Student.objects.get(student_id=row["student_id"])
            if row.get("student_name") and row["student_name"].casefold() != student.full_name.casefold():
                raise ValueError("student_name does not match student_id")
            timing = calculate_attendance_status(scheduled_time, check_in_time) if check_in_time else {'status': 'absent', 'attendance_code': supplied_status or 'ABSENT'}
            if check_in_time:
                _validate_status(row, timing)

            existing_id = AttendanceRecord.objects.filter(attendance_id=attendance_id).first()
            if existing_id and (existing_id.student_id != student.id or existing_id.session_id != session.id):
                raise ValueError("attendance_id belongs to another student or session")
            existing_pair = AttendanceRecord.objects.filter(session=session, student=student).first()
            if existing_pair and existing_pair.attendance_id not in (None, attendance_id):
                raise ValueError("session + student already has another attendance_id")

            if check_in_time:
                record, created, _ = record_attendance_event(
                    session=session,
                    student=student,
                    check_in_at=check_in_time,
                    method=row.get("method") or "FACIAL_RECOGNITION",
                    device_id=row.get("device_id", ""),
                    preferred_attendance_id=attendance_id if not existing_pair else None,
                    require_active=False,
                )
            else:
                record, created = record_absence_event(
                    session=session,
                    student=student,
                    device_id=row.get("device_id") or "SYSTEM-FINALIZE",
                    preferred_attendance_id=attendance_id if not existing_pair else None,
                )
            if not created:
                result.duplicates += 1
            else:
                result.imported += 1
        except Exception as error:
            result.failed.append({"row": row_number, "error": str(error), "source": source})
    return result


def import_csv_bytes(content: bytes, *, source="csv"):
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    headers = {str(header or "").strip().lower().lstrip("\ufeff") for header in (reader.fieldnames or [])}
    missing = sorted(REQUIRED_COLUMNS - headers)
    if missing:
        return ImportResult(failed=[{"row": 1, "error": f"missing columns: {', '.join(missing)}", "source": source}])
    return import_rows(reader, source=source)


def import_csv_file(path):
    with open(path, "rb") as stream:
        return import_csv_bytes(stream.read(), source=os.fspath(path))
