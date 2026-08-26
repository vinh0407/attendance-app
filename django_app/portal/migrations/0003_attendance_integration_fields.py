from django.db import migrations, models


def backfill_integration_fields(apps, schema_editor):
    Session = apps.get_model('portal', 'AttendanceSession')
    Record = apps.get_model('portal', 'AttendanceRecord')
    starts = {1: (7, 0), 2: (7, 50), 3: (8, 50), 4: (9, 40), 5: (10, 40), 6: (13, 0), 7: (13, 50), 8: (14, 50), 9: (15, 40), 10: (16, 40)}
    for session in Session.objects.select_related('schedule__subject', 'schedule__classroom').all():
        subject = ''.join(ch for ch in session.schedule.subject.code.upper() if ch.isalnum()) or 'SESSION'
        room = ''.join(ch for ch in session.schedule.room.upper() if ch.isalnum()) or 'ROOM'
        session.external_session_id = f'SES-{session.date:%Y%m%d}-{subject}-{room}-{session.pk:02d}'
        session.save(update_fields=['external_session_id'])
    for record in Record.objects.select_related('session__schedule__subject').order_by('date', 'id'):
        record.attendance_id = f'ATT-{record.date:%Y%m%d}-{record.pk:04d}'
        record.method = record.method or 'FACIAL_RECOGNITION'
        if record.session:
            hour, minute = starts.get(record.session.schedule.start_period, (7, 0))
            import datetime
            record.scheduled_time = datetime.time(hour, minute)
            if record.time_in:
                scheduled = datetime.datetime.combine(record.date, record.scheduled_time)
                check_in = datetime.datetime.combine(record.date, record.time_in)
                late = max(0, int((check_in - scheduled).total_seconds() // 60))
                record.late_minutes = late
                if late <= 0:
                    record.attendance_code, record.attendance_label = 'ON_TIME', 'ĐÚNG GIỜ'
                elif late <= 15:
                    record.attendance_code, record.attendance_label = 'LATE_LEVEL_1', 'TRỄ — LEVEL 1'
                elif late < 60:
                    record.attendance_code, record.attendance_label = 'LATE_ONE_PERIOD', 'TRỄ — 1 PERIOD'
                elif late <= 120:
                    record.attendance_code, record.attendance_label = 'ABSENT_TWO_PERIODS', 'VẮNG — 2 PERIODS'
                else:
                    record.attendance_code, record.attendance_label = 'ABSENT', 'VẮNG'
        record.save(update_fields=['attendance_id', 'method', 'scheduled_time', 'late_minutes', 'attendance_code', 'attendance_label'])


class Migration(migrations.Migration):
    dependencies = [
        ('portal', '0002_add_schedule_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancesession',
            name='external_session_id',
            field=models.CharField(blank=True, max_length=80, null=True, unique=True, verbose_name='Mã phiên tích hợp'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='attendance_id',
            field=models.CharField(blank=True, max_length=40, null=True, unique=True, verbose_name='Mã điểm danh'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='attendance_code',
            field=models.CharField(blank=True, max_length=40, verbose_name='Mã trạng thái'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='attendance_label',
            field=models.CharField(blank=True, max_length=80, verbose_name='Nhãn trạng thái'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='attendance_periods',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Số tiết bị tính'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='device_id',
            field=models.CharField(blank=True, max_length=80, verbose_name='Thiết bị'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='late_minutes',
            field=models.PositiveIntegerField(default=0, verbose_name='Số phút trễ'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='method',
            field=models.CharField(default='FACIAL_RECOGNITION', max_length=40, verbose_name='Phương thức'),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='scheduled_time',
            field=models.TimeField(blank=True, null=True, verbose_name='Giờ học dự kiến'),
        ),
        migrations.RunPython(backfill_integration_fields, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='attendancerecord',
            constraint=models.UniqueConstraint(fields=('session', 'student'), name='uniq_attendance_session_student'),
        ),
    ]
