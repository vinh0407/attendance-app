"""
Management command: Test nhận diện khuôn mặt từ 1 ảnh
Dùng lệnh: python manage.py test_recognize --image path/to/image.jpg
Hoặc test tất cả ảnh trong my_faces:
python manage.py test_recognize --all
"""
import os
import cv2
import numpy as np
from django.core.management.base import BaseCommand
from django.utils import timezone
from portal.models import Student, AttendanceRecord


class Command(BaseCommand):
    help = 'Test face recognition and attendance recording.'

    def add_arguments(self, parser):
        parser.add_argument('--image', type=str, help='Path to the image to recognize.')
        parser.add_argument('--all', action='store_true', help='Test every image in my_faces/.')
        parser.add_argument('--no-save', action='store_true', help='Recognize faces without recording attendance.')

    def handle(self, *args, **options):
        from portal import face_recognition as fr

        self.stdout.write('🔄 Loading the InsightFace model...')
        app = fr.get_face_app()
        self.stdout.write(self.style.SUCCESS('✅ Model loaded.'))
        self.stdout.write('')

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

        if options['all']:
            # Test tất cả ảnh trong my_faces
            my_faces_dir = os.path.join(base_dir, 'my_faces')
            self.stdout.write(f'📁 my_faces directory: {my_faces_dir}')
            self.stdout.write('=' * 60)

            for person_name in os.listdir(my_faces_dir):
                person_dir = os.path.join(my_faces_dir, person_name)
                if not os.path.isdir(person_dir):
                    continue

                self.stdout.write(f'\n👤 Testing person: {person_name}')
                images = [f for f in os.listdir(person_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

                for img_file in images[:2]:  # Test tối đa 2 ảnh mỗi người
                    img_path = os.path.join(person_dir, img_file)
                    self._test_image(fr, img_path, options['no_save'])

        elif options['image']:
            img_path = options['image']
            if not os.path.exists(img_path):
                self.stdout.write(self.style.ERROR(f'❌ File not found: {img_path}'))
                return
            self._test_image(fr, img_path, options['no_save'])

        else:
            # Test với ảnh test.jpeg trong thư mục gốc
            test_images = [
                os.path.join(base_dir, 'test.jpeg'),
                os.path.join(base_dir, 'test2.jpg'),
            ]
            for img_path in test_images:
                if os.path.exists(img_path):
                    self.stdout.write(f'\n📸 Testing image: {os.path.basename(img_path)}')
                    self._test_image(fr, img_path, options['no_save'])
                else:
                    self.stdout.write(self.style.WARNING(f'⚠️  Missing: {img_path}'))

            self.stdout.write('\n💡 Tip: Use --image <path> for one image or --all to test every image.')

        # Hiển thị kết quả điểm danh hôm nay
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write("📊 TODAY'S ATTENDANCE:")
        today = timezone.localdate()
        records = AttendanceRecord.objects.filter(date=today).select_related('student')
        if records.exists():
            for r in records:
                conf = f'{r.confidence*100:.1f}%' if r.confidence else 'N/A'
                time_str = r.time_in.strftime('%H:%M:%S') if r.time_in else 'N/A'
                self.stdout.write(
                    f'  ✅ {r.student.full_name} ({r.student.student_id}) - '
                    f'{r.get_status_display()} - {time_str} - Confidence: {conf}'
                )
        else:
            self.stdout.write('  No attendance records have been created today.')

    def _test_image(self, fr, img_path, no_save=False):
        """Test nhận diện 1 ảnh"""
        frame = cv2.imread(img_path)
        if frame is None:
            self.stdout.write(self.style.ERROR(f'  ❌ Unable to read image: {img_path}'))
            return

        h, w = frame.shape[:2]
        self.stdout.write(f'  📐 Dimensions: {w}x{h}')

        # Nhận diện
        results = fr.recognize_face(frame)

        if not results:
            self.stdout.write(self.style.WARNING('  ⚠️  No faces detected.'))
            return

        self.stdout.write(f'  🔍 Detected {len(results)} face(s):')
        for i, r in enumerate(results, 1):
            name = r['name']
            conf = r['confidence']
            bbox = r['bbox']
            status_icon = '✅' if name != 'Unknown' else '❓'
            self.stdout.write(
                f'    [{i}] {status_icon} {name} - Confidence: {conf:.1f}% - BBox: {bbox}'
            )

            # Ghi điểm danh nếu nhận diện được và không ở chế độ no_save
            if name != 'Unknown' and not no_save:
                try:
                    student = Student.objects.filter(full_name=name).first()
                    if student:
                        current_time = timezone.now()
                        record, created = AttendanceRecord.objects.update_or_create(
                            student=student,
                            date=current_time.date(),
                            session=None,
                            defaults={
                                'time_in': current_time.time(),
                                'status': 'present',
                                'confidence': conf / 100.0,
                            }
                        )
                        action = '🆕 New attendance' if created else '🔄 Updated attendance'
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'    → {action}: {student.full_name} ({student.student_id}) '
                                f'at {current_time.strftime("%H:%M:%S")}'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'    ⚠️  "{name}" was not found in the student database. Run sync_faces first.')
                        )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'    ❌ Attendance recording failed: {e}'))
