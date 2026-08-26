"""Import grade ledger CSV files from the Admin data directory."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from portal.models import Grade, Student, Subject


def normalise(value):
    return re.sub(r'[^a-z0-9]+', '_', str(value or '').strip().lower()).strip('_')


ALIASES = {
    'student_id': {'student_id', 'studentid', 'mssv', 'ma_sv'},
    'subject_id': {'subject_id', 'subject_code', 'subject', 'ma_mon'},
    'semester': {'semester', 'term', 'hoc_ky'},
    'assessment_type': {'assessment_type', 'type', 'loai_diem'},
    'score': {'score', 'mark', 'diem'},
}


def map_row(raw):
    row = {normalise(k): str(v or '').strip() for k, v in raw.items()}
    return {target: next((row[key] for key in keys if row.get(key)), '') for target, keys in ALIASES.items()}


class Command(BaseCommand):
    help = 'Import student grades from CSV files in APP/Dữ liệu/Admin.'

    def add_arguments(self, parser):
        parser.add_argument('input', nargs='?', default=None, help='CSV file or directory')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        source = Path(options['input'] or settings.BASE_DIR.parent / 'APP' / 'Dữ liệu' / 'Admin').resolve()
        if source.is_file():
            files = [source]
        elif source.is_dir():
            files = sorted(source.rglob('*.csv'))
        else:
            raise CommandError(f'Input path does not exist: {source}')
        if not files:
            self.stdout.write(self.style.WARNING('No grade CSV files found in the Admin data directory.'))
            return
        created = updated = rejected = 0
        for path in files:
            with path.open('r', encoding='utf-8-sig', newline='') as stream:
                for line, raw in enumerate(csv.DictReader(stream), start=2):
                    row = map_row(raw)
                    try:
                        if not row['student_id'] or not row['subject_id'] or not row['score']:
                            raise ValueError('student_id, subject_id and score are required')
                        student = Student.objects.get(student_id=row['student_id'])
                        subject = Subject.objects.get(code=row['subject_id'])
                        defaults = {
                            'semester': row['semester'],
                            'score': row['score'],
                        }
                        key = {
                            'student': student,
                            'subject': subject,
                            'semester': row['semester'],
                            'assessment_type': row['assessment_type'] or 'TOTAL',
                        }
                        if not options['dry_run']:
                            _, was_created = Grade.objects.update_or_create(defaults=defaults, **key)
                            created += int(was_created)
                            updated += int(not was_created)
                    except (Student.DoesNotExist, Subject.DoesNotExist, ValueError) as exc:
                        rejected += 1
                        self.stdout.write(self.style.WARNING(f'{path}:{line} {exc}'))
        self.stdout.write(self.style.SUCCESS(f'Files: {len(files)} | created: {created} | updated: {updated} | rejected: {rejected}'))
