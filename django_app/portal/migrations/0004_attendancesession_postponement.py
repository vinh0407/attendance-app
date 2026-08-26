from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0003_attendance_integration_fields')]

    operations = [
        migrations.AddField(
            model_name='attendancesession', name='postponed_to',
            field=models.DateField(blank=True, null=True, verbose_name='Ngày dời lịch'),
        ),
        migrations.AddField(
            model_name='attendancesession', name='postponed_reason',
            field=models.CharField(blank=True, max_length=240, verbose_name='Lý do hoãn'),
        ),
    ]
