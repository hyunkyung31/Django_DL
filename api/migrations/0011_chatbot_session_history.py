# Generated manually for patient AI chatbot sessions/history

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0010_appointment"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatSession",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("patient_id", models.CharField(db_index=True, max_length=50)),
                (
                    "title",
                    models.CharField(default="새로운 상담", max_length=200),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "chat_sessions",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="ChatHistory",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("user", "사용자"),
                            ("assistant", "AI"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("content", models.TextField()),
                ("intent", models.CharField(blank=True, default="", max_length=50)),
                ("risk_level", models.IntegerField(default=0)),
                (
                    "exam_id",
                    models.IntegerField(blank=True, db_index=True, null=True),
                ),
                ("ai_result_id", models.IntegerField(blank=True, null=True)),
                (
                    "reference_type",
                    models.CharField(
                        choices=[
                            ("general", "일반"),
                            ("symptom", "증상 상담"),
                            ("report", "검사 결과"),
                            ("medical", "의학 용어"),
                            ("appointment", "예약"),
                            ("lifestyle", "생활습관"),
                        ],
                        default="general",
                        max_length=30,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="api.chatsession",
                    ),
                ),
            ],
            options={
                "db_table": "chat_history",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="chathistory",
            index=models.Index(
                fields=["session", "created_at"],
                name="chat_history_session_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="chathistory",
            index=models.Index(
                fields=["exam_id"],
                name="chat_history_exam_idx",
            ),
        ),
    ]
