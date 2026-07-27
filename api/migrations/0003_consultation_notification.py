from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_bookmark"),
    ]

    operations = [
        migrations.CreateModel(
            name="Consultation",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("patient_id", models.CharField(max_length=50)),
                ("requester_id", models.CharField(max_length=20)),
                ("receiver_id", models.CharField(db_index=True, max_length=20)),
                ("reason", models.TextField()),
                ("status", models.CharField(default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "consultations",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("recipient_doctor_id", models.CharField(db_index=True, max_length=20)),
                (
                    "notification_type",
                    models.CharField(default="consultation", max_length=30),
                ),
                ("title", models.CharField(max_length=200)),
                ("message", models.TextField()),
                (
                    "consultation_id",
                    models.CharField(blank=True, max_length=50, null=True),
                ),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "notifications",
                "ordering": ["-created_at"],
            },
        ),
    ]
