"""Import attendance history stored below date/subject folders."""
from pathlib import Path
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from portal.attendance_import import import_csv_file


class Command(BaseCommand):
    help = 'Import CSV attendance history from APP/Dữ liệu/Lịch sử điểm danh recursively.'

    def add_arguments(self, parser):
        parser.add_argument('input', nargs='?', default=None, help='Date/subject folder or CSV file')

    def handle(self, *args, **options):
        source = Path(options['input'] or settings.ATTENDANCE_HISTORY_DIR).resolve()
        if source.is_file():
            files = [source]
        elif source.is_dir():
            files = sorted(source.rglob('*.csv'))
        else:
            raise CommandError(f'Input path does not exist: {source}')
        if not files:
            self.stdout.write(self.style.WARNING(f'No attendance CSV files found in {source}'))
            return
        totals = {'files': 0, 'imported': 0, 'duplicates': 0, 'failed_rows': 0}
        for path in files:
            result = import_csv_file(path)
            totals['files'] += 1
            totals['imported'] += result.imported
            totals['duplicates'] += result.duplicates
            totals['failed_rows'] += len(result.failed)
            self.stdout.write(json.dumps({'file': str(path), 'imported': result.imported, 'duplicates': result.duplicates, 'failed': result.failed}, ensure_ascii=False))
        self.stdout.write(self.style.SUCCESS(json.dumps(totals, ensure_ascii=False)))
