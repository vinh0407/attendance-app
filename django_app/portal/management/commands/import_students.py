"""Import the school's student roster without creating synthetic records."""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from portal.models import Student


ALIASES = {
    'student_id': {'student_id', 'studentid', 'mssv', 'ma_sinh_vien', 'ma_sv', 'id'},
    'full_name': {'full_name', 'fullname', 'name', 'student_name', 'ho_ten', 'ho_va_ten', 'hoten'},
    'class_name': {'class_name', 'class', 'lop', 'ten_lop'},
    'email': {'email', 'mail'},
}


def normalise(value):
    text = unicodedata.normalize('NFKD', str(value or '').strip().lower())
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', '_', text).strip('_')


def map_row(raw):
    normal = {normalise(k): str(v or '').strip() for k, v in raw.items()}
    result = {}
    for target, keys in ALIASES.items():
        result[target] = next((normal[key] for key in keys if normal.get(key)), '')
    return result


def read_records(path: Path):
    if path.suffix.lower() in {'.json', '.jsonl'}:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
        return payload if isinstance(payload, list) else payload.get('students', [])
    with path.open('r', encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream, delimiter='\t' if path.suffix.lower() == '.tsv' else ','))


class Command(BaseCommand):
    help = 'Import student roster CSV/TSV/JSON files from the configured school data directory.'

    def add_arguments(self, parser):
        parser.add_argument('input', nargs='?', default=None, help='Roster file or directory (defaults to APP/Dữ liệu/Sinh viên trường)')
        parser.add_argument('--dry-run', action='store_true', help='Validate and report without writing')

    def handle(self, *args, **options):
        source = Path(options['input'] or settings.STUDENT_DATA_DIR).resolve()
        if source.is_file():
            files = [source]
        elif source.is_dir():
            files = sorted(p for p in source.rglob('*') if p.suffix.lower() in {'.csv', '.tsv', '.json', '.jsonl'})
        else:
            raise CommandError(f'Input path does not exist: {source}')
        if not files:
            self.stdout.write(self.style.WARNING(f'No student files found in {source}'))
            return
        created = updated = rejected = 0
        for path in files:
            for row_number, raw in enumerate(read_records(path), start=2):
                row = map_row(raw)
                if not row['student_id'] or not row['full_name']:
                    rejected += 1
                    self.stdout.write(self.style.WARNING(f'{path}:{row_number} missing student_id/full_name'))
                    continue
                if options['dry_run']:
                    continue
                student, was_created = Student.objects.update_or_create(
                    student_id=row['student_id'],
                    defaults={'full_name': row['full_name'], 'class_name': row['class_name'], 'email': row['email']},
                )
                created += int(was_created)
                updated += int(not was_created)
        self.stdout.write(self.style.SUCCESS(f'Files: {len(files)} | created: {created} | updated: {updated} | rejected: {rejected}'))
