from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0004_attendancesession_postponement')]

    operations = [
        migrations.AlterField(
            model_name='attendancesession',
            name='status',
            field=models.CharField(
                choices=[
                    ('scheduled', 'Đã lên lịch'),
                    ('active', 'Đang điểm danh'),
                    ('completed', 'Đã kết thúc'),
                    ('cancelled', 'Đã hủy'),
                    ('postponed', 'Hoãn'),
                ], max_length=20, default='scheduled', verbose_name='Trạng thái',
            ),
        ),
    ]
