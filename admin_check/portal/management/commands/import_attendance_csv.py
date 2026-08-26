import json
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from portal.attendance_import import import_csv_file


class Command(BaseCommand):
    help = "Import validated attendance CSV rows into Django's central database."

    def add_arguments(self, parser):
        parser.add_argument("input", nargs="?", default=None, help="CSV file or directory containing CSV files (defaults to the kiosk inbox)")
        parser.add_argument("--archive", action="store_true", help="Move files to processed/ or failed/ after import")
        parser.add_argument("--processed-dir", help="Directory for successful files")
        parser.add_argument("--failed-dir", help="Directory for files with rejected rows")

    def handle(self, *args, **options):
        source = Path(options["input"] or settings.ATTENDANCE_IMPORT_DIR).resolve()
        if source.is_file():
            files = [source]
        elif source.is_dir():
            files = sorted(source.rglob("*.csv"))
        else:
            raise CommandError(f"Input path does not exist: {source}")
        if not files:
            self.stdout.write(self.style.WARNING("No CSV files found."))
            return

        processed = Path(options["processed_dir"] or source.parent / "processed")
        failed = Path(options["failed_dir"] or source.parent / "failed")
        total = {"files": 0, "imported": 0, "duplicates": 0, "failed_rows": 0}
        for path in files:
            result = import_csv_file(path)
            total["files"] += 1
            total["imported"] += result.imported
            total["duplicates"] += result.duplicates
            total["failed_rows"] += len(result.failed)
            payload = {"file": str(path), "imported": result.imported, "duplicates": result.duplicates, "failed": result.failed}
            self.stdout.write(json.dumps(payload, ensure_ascii=False))
            if options["archive"]:
                destination_dir = failed if result.failed else processed
                destination_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(destination_dir / path.name))
        self.stdout.write(self.style.SUCCESS(json.dumps(total, ensure_ascii=False)))
