from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0006_rename_reference_type_consultation_reference_types"),
    ]

    operations = [
        migrations.AlterField(
            model_name="consultation",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "대기"),
                    ("in_progress", "검토중"),
                    ("accepted", "수락됨"),
                    ("rejected", "거절됨"),
                    ("completed", "완료"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="consultation",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
