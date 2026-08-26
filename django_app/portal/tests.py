import datetime
import csv
import io
import json
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, override_settings

from .attendance_service import calculate_attendance_status, finalize_session_attendance, record_attendance_event
from .attendance_import import import_csv_bytes
from .attendance_archive import archive_attendance_record
from .models import AttendanceRecord, AttendanceSession, ClassRoom, Grade, Schedule, Student, Subject


class AttendanceTimingTests(SimpleTestCase):
    def test_spec_boundaries(self):
        scheduled = datetime.time(7, 30)
        cases = [
            ('07:29:00', 'ON_TIME'),
            ('07:30:00', 'ON_TIME'),
            ('07:31:00', 'LATE_LEVEL_1'),
            ('07:45:00', 'LATE_LEVEL_1'),
            ('07:45:59', 'LATE_LEVEL_1'),
            ('07:46:00', 'LATE_ONE_PERIOD'),
            ('08:29:00', 'LATE_ONE_PERIOD'),
            ('08:30:00', 'ABSENT_TWO_PERIODS'),
            ('09:30:00', 'ABSENT_TWO_PERIODS'),
            ('09:31:00', 'ABSENT'),
        ]
        for check_in, expected_code in cases:
            with self.subTest(check_in=check_in):
                result = calculate_attendance_status(scheduled, datetime.time.fromisoformat(check_in))
                self.assertEqual(result['attendance_code'], expected_code)


class AttendanceCsvIntegrationTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(student_id='2251129999', full_name='CSV Student')
        classroom = ClassRoom.objects.create(class_id='CSV01', name='CSV Class')
        classroom.students.add(self.student)
        subject = Subject.objects.create(code='CSV101', name='CSV Integration')
        schedule = Schedule.objects.create(
            subject=subject,
            classroom=classroom,
            day_of_week=2,
            start_period=1,
            end_period=2,
            room='A203',
        )
        self.session = AttendanceSession.objects.create(
            schedule=schedule,
            external_session_id='SES-CSV-001',
            date=datetime.date(2026, 8, 26),
            status='completed',
        )

    def test_import_uses_shared_record_and_is_idempotent(self):
        csv_text = (
            'attendance_id,session_id,student_id,student_name,class_id,subject_id,subject_name,date,'
            'scheduled_time,check_in_time,late_minutes,status,attendance_code,attendance_label,'
            'attendance_periods,method,device_id\n'
            'ATT-20260826-9001,SES-CSV-001,2251129999,CSV Student,CSV01,CSV101,CSV Integration,'
            '2026-08-26,07:00:00,07:05:00,5,late,LATE_LEVEL_1,"TRỄ — LEVEL 1",0,'
            'FACIAL_RECOGNITION,KIOSK-A203\n'
        ).encode('utf-8')
        first = import_csv_bytes(csv_text, source='test.csv')
        second = import_csv_bytes(csv_text, source='test.csv')
        self.assertEqual(first.imported, 1)
        self.assertEqual(first.failed, [])
        self.assertEqual(second.duplicates, 1)
        record = self.student.attendance_records.get(session=self.session)
        self.assertEqual(record.attendance_id, 'ATT-20260826-9001')
        self.assertEqual(record.attendance_code, 'LATE_LEVEL_1')
        self.assertEqual(record.device_id, 'KIOSK-A203')

    def test_import_accepts_kiosk_uppercase_status_values(self):
        csv_text = (
            'attendance_id,session_id,student_id,student_name,subject_id,subject_name,date,'
            'scheduled_time,check_in_time,late_minutes,status,attendance_periods,method,device_id\n'
            'ATT-20260826-9002,SES-CSV-001,2251129999,CSV Student,CSV101,CSV Integration,'
            '2026-08-26,07:00:00,07:05:00,5,LATE_LEVEL_1,0,FACIAL_RECOGNITION,KIOSK-A203\n'
        ).encode('utf-8')
        result = import_csv_bytes(csv_text, source='kiosk.csv')
        self.assertEqual(result.imported, 1)

    def test_admin_can_create_class_and_postpone_session(self):
        client = Client()
        response = client.post('/api/classes/create/', data=json.dumps({
            'class_id': 'NEW01', 'name': 'New class', 'department': 'IT',
        }), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        response = client.post(
            f'/api/session/{self.session.id}/postpone/',
            data=json.dumps({'postponed_to': '2026-08-30', 'reason': 'Room maintenance'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'postponed')
        self.assertEqual(self.session.postponed_to, datetime.date(2026, 8, 30))
        self.assertTrue(AttendanceSession.objects.filter(schedule=self.session.schedule, date=datetime.date(2026, 8, 30), status='scheduled').exists())

    def test_export_all_csv_has_consistent_rows(self):
        response = Client().get('/api/export/all.csv')
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertGreaterEqual(len(rows), 2)
        self.assertTrue(all(len(row) == len(rows[0]) for row in rows))

    def test_finalize_creates_absent_record_and_archives_csv(self):
        missing = Student.objects.create(student_id='2251128888', full_name='Missing Student')
        self.session.schedule.classroom.students.add(missing)
        self.session.status = 'active'
        self.session.save(update_fields=['status'])
        with tempfile.TemporaryDirectory() as temp_dir, override_settings(ATTENDANCE_HISTORY_DIR=Path(temp_dir)):
            with self.captureOnCommitCallbacks(execute=True):
                created = finalize_session_attendance(self.session)
            self.assertEqual(created, 2)
            record = AttendanceRecord.objects.get(session=self.session, student=missing)
            self.assertEqual(record.status, 'absent')
            self.assertEqual(record.attendance_periods, 2)
            path = Path(temp_dir) / '26_08_2026' / 'CSV Integration' / 'attendance.csv'
            self.assertTrue(path.exists())
            self.assertIn('Missing Student', path.read_text(encoding='utf-8-sig'))

    def test_student_grades_and_subject_summary_are_scoped(self):
        user = User.objects.create_user('grade-user')
        self.student.user = user
        self.student.save(update_fields=['user'])
        Grade.objects.create(student=self.student, subject=self.session.schedule.subject, semester='2026-1', score='8.50')
        client = Client()
        client.force_login(user)
        grades = client.get('/api/student/me/grades/')
        summary = client.get('/api/student/me/subjects/summary/')
        self.assertEqual(grades.status_code, 200)
        self.assertEqual(grades.json()['data'][0]['score'], 8.5)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()['data'][0]['subject_id'], 'CSV101')
