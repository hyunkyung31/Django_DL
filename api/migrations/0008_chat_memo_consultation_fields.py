from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_consultation_status_updated_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="consultation",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="is_read",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="consultation",
            name="read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consultation",
            name="response_memo",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="consultation",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notification",
            name="chat_message_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notification",
            name="chat_room_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notification",
            name="read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="ChatRoom",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("doctor1_id", models.CharField(db_index=True, max_length=20)),
                ("doctor2_id", models.CharField(db_index=True, max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "chat_rooms",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="Memo",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("doctor_id", models.CharField(db_index=True, max_length=20)),
                (
                    "patient_id",
                    models.CharField(
                        blank=True, db_index=True, max_length=50, null=True
                    ),
                ),
                ("exam_id", models.IntegerField(blank=True, null=True)),
                (
                    "memo_type",
                    models.CharField(
                        choices=[("text", "텍스트"), ("voice", "음성")],
                        default="text",
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                ("content", models.TextField(blank=True, default="")),
                (
                    "audio_file",
                    models.FileField(
                        blank=True, null=True, upload_to="memos/audio/%Y/%m/%d/"
                    ),
                ),
                (
                    "audio_duration_seconds",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("transcript", models.TextField(blank=True, default="")),
                (
                    "transcription_status",
                    models.CharField(
                        choices=[
                            ("none", "없음"),
                            ("processing", "처리중"),
                            ("completed", "완료"),
                            ("failed", "실패"),
                        ],
                        default="none",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "memos",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="ChatMessage",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("sender_id", models.CharField(db_index=True, max_length=20)),
                ("receiver_id", models.CharField(db_index=True, max_length=20)),
                (
                    "message_type",
                    models.CharField(
                        choices=[
                            ("text", "텍스트"),
                            ("patient", "환자 자료"),
                            ("examination", "검사 자료"),
                            ("ai_result", "AI 분석 결과"),
                            ("consultation", "협진 요청"),
                        ],
                        db_index=True,
                        default="text",
                        max_length=20,
                    ),
                ),
                ("content", models.TextField(blank=True, default="")),
                (
                    "patient_id",
                    models.CharField(
                        blank=True, db_index=True, max_length=50, null=True
                    ),
                ),
                ("exam_id", models.IntegerField(blank=True, null=True)),
                ("ai_result_id", models.IntegerField(blank=True, null=True)),
                ("consultation_id", models.BigIntegerField(blank=True, null=True)),
                ("is_read", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                (
                    "resource_status",
                    models.CharField(
                        choices=[
                            ("unread", "안 읽음"),
                            ("checked", "확인함"),
                            ("answered", "답변 완료"),
                        ],
                        default="unread",
                        max_length=20,
                    ),
                ),
                ("checked_at", models.DateTimeField(blank=True, null=True)),
                ("answered_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="api.chatroom",
                    ),
                ),
            ],
            options={
                "db_table": "chat_messages",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="chatroom",
            constraint=models.UniqueConstraint(
                fields=("doctor1_id", "doctor2_id"),
                name="unique_doctor_chat_room",
            ),
        ),
        migrations.AddConstraint(
            model_name="chatroom",
            constraint=models.CheckConstraint(
                check=models.Q(doctor1_id__lt=models.F("doctor2_id")),
                name="chat_doctor_order_check",
            ),
        ),
        migrations.AddIndex(
            model_name="chatmessage",
            index=models.Index(
                fields=["room", "created_at"],
                name="chat_message_room_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="chatmessage",
            index=models.Index(
                fields=["receiver_id", "is_read"],
                name="chat_receiver_read_idx",
            ),
        ),
    ]
