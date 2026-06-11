"""
Management command: Đồng bộ face_database.pkl → Django Student model
Dùng lệnh: python manage.py sync_faces
"""
import pickle
import os
from django.core.management.base import BaseCommand
from portal.models import Student


class Command(BaseCommand):
    help = 'Đồng bộ face_database.pkl vào Django Student database'

    def handle(self, *args, **options):
        # Đường dẫn face_database.pkl
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        db_file = os.path.join(base_dir, 'face_database.pkl')
        my_faces_dir = os.path.join(base_dir, 'my_faces')

        if not os.path.exists(db_file):
            self.stdout.write(self.style.ERROR(f'Không tìm thấy file: {db_file}'))
            return

        # Đọc face database
        with open(db_file, 'rb') as f:
            face_db = pickle.load(f)

        self.stdout.write(f'📦 Tìm thấy {len(face_db)} người trong face database:')
        for name in face_db.keys():
            self.stdout.write(f'   - {name} ({len(face_db[name])} embeddings)')

        self.stdout.write('')
        created_count = 0
        updated_count = 0

        for idx, (name, embeddings) in enumerate(face_db.items(), start=1):
            # Tìm student theo tên (full_name)
            student = Student.objects.filter(full_name=name).first()

            # Tạo student_id tự động nếu chưa có
            # Thang → SV001, Viet → SV002, Anh vu → SV003, chuong → SV004, ...
            auto_id = f'SV{idx:03d}'

            # Xác định class_name (mặc định CNTT01 nếu chưa có)
            class_name_default = 'CNTT01'

            if student:
                # Đã có → cập nhật is_registered
                student.is_registered = True
                student.save()
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'🔄 Đã có: {name} (ID: {student.student_id})'))
            else:
                # Chưa có → tạo mới
                # Tránh trùng student_id
                while Student.objects.filter(student_id=auto_id).exists():
                    auto_id_num = int(auto_id[2:]) + 10
                    auto_id = f'SV{auto_id_num:03d}'

                student = Student.objects.create(
                    student_id=auto_id,
                    full_name=name,
                    class_name=class_name_default,
                    is_registered=True,
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Tạo mới: {name} → {auto_id}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'🎉 Hoàn thành! Tạo mới: {created_count}, Cập nhật: {updated_count}'
        ))
        self.stdout.write(f'📊 Tổng sinh viên trong DB: {Student.objects.count()}')
