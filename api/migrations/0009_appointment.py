from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0008_chat_memo_consultation_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="Appointment",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("patient_id", models.CharField(db_index=True, max_length=50)),
                ("doctor_id", models.CharField(db_index=True, max_length=20)),
                ("department", models.CharField(max_length=50)),
                ("scheduled_at", models.DateTimeField(db_index=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("requested", "신청"),
                            ("confirmed", "확정"),
                            ("cancelled", "취소"),
                            ("completed", "완료"),
                        ],
                        db_index=True,
                        default="requested",
                        max_length=20,
                    ),
                ),
                ("memo", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "appointments",
                "ordering": ["-scheduled_at", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["doctor_id", "scheduled_at"],
                name="appt_doctor_sched_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["patient_id", "scheduled_at"],
                name="appt_patient_sched_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["doctor_id", "status"],
                name="appt_doctor_status_idx",
            ),
        ),
    ]
