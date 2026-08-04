from django.db import models

class Doctor(models.Model):
    doctor_id = models.CharField(max_length=20, primary_key=True)
    password = models.CharField(max_length=128)
    doctor_name = models.CharField(max_length=50)
    department = models.CharField(max_length=50)
    hospital_name = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=20)
    email = models.CharField(max_length=100)
    created_at = models.DateTimeField()

    class Meta :
        db_table = "doctors"
        managed = False

    def __str__(self):
        return f'{self.doctor_id} ({self.doctor_name})'

class Patient(models.Model):
    patient_id = models.CharField(max_length=50, primary_key=True)
    primary_doctor_id = models.CharField(max_length=50, null=True, blank=True)
    email = models.CharField(max_length=100, null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    kakao_id = models.CharField(max_length=100, null=True, blank=True)
    social_provider = models.CharField(max_length=20, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    dataset_patient_id = models.CharField(max_length=20)
    patient_name = models.CharField(max_length=20)
    gender = models.CharField(max_length=1, null=True, blank=True)
    age = models.IntegerField()
    history_score = models.IntegerField(null=True, blank=True)
    ecg_result = models.CharField(max_length=50, null=True, blank=True)
    risk_factors_count = models.IntegerField(null=True, blank=True)
    troponin_t_level = models.FloatField(null=True, blank=True)
    underlying_diseases = models.JSONField(null=True, blank=True)
    chief_complaint = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "patients"
        managed = False

    def __str__(self):
        return f"{self.patient_id} ({self.patient_name})"

class Examination(models.Model):
    exam_id = models.IntegerField(primary_key=True)
    patient_id = models.CharField(max_length=50)
    vessel_type = models.CharField(max_length=20)
    video_path = models.CharField(max_length=255)
    key_frame_path = models.CharField(max_length=255)
    class Meta:
        db_table = "examinations"
        managed = False
    def __str__(self):
        return f"{self.exam_id} ({self.patient_id})"

class AIResult(models.Model):
    exam_id = models.IntegerField(primary_key=True)
    confirming_doctor_id = models.CharField(max_length=50, null=True, blank=True)
    has_lesion = models.BooleanField()
    severity_class = models.CharField(max_length=50)
    confidence_score = models.FloatField()
    ai_bbox_data = models.JSONField(null=True, blank=True)
    gradcam_path = models.CharField(max_length=255, null=True, blank=True)
    heart_score = models.IntegerField(null=True, blank=True)
    mace_risk_percent = models.FloatField(null=True, blank=True)
    doctor_opinion = models.TextField(null=True, blank=True)
    is_confirmed = models.BooleanField(default=False)
    class Meta:
        db_table = "ai_results"
        managed = False
    def __str__(self):
        return f"AIResult({self.exam_id})"

class Bookmark(models.Model):
    id = models.BigAutoField(primary_key=True)
    doctor_id = models.CharField(max_length=20)
    patient_id = models.CharField(max_length=50, null=True, blank=True)
    exam_id = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=200)
    note = models.TextField(null=True, blank=True)
    frame_number = models.IntegerField(null=True, blank=True)
    bbox_data = models.JSONField()
    snapshot_path = models.CharField(max_length=512, null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "bookmarks"
        managed = False

    def __str__(self):
        return f"Bookmark({self.id}, {self.title})"


class Consultation(models.Model):
    """협진 요청. Doctor는 unmanaged라 FK 대신 doctor_id 문자열을 사용."""

    class Status(models.TextChoices):
        PENDING = "pending", "대기"
        IN_PROGRESS = "in_progress", "검토중"
        ACCEPTED = "accepted", "수락됨"
        REJECTED = "rejected", "거절됨"
        COMPLETED = "completed", "완료"

    id = models.BigAutoField(primary_key=True)
    patient_id = models.CharField(max_length=50)
    requester_id = models.CharField(max_length=20, db_index=True)
    receiver_id = models.CharField(max_length=20, db_index=True)
    reason = models.TextField()
    priority = models.CharField(max_length=20, default="normal")
    memo = models.TextField(blank=True, default="")
    reference_types = models.JSONField(default=list, blank=True)
    exam_id = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    response_memo = models.TextField(blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "consultations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Consultation({self.id}, {self.patient_id} → {self.receiver_id})"


class ChatRoom(models.Model):
    """의사 두 명 사이의 1:1 채팅방."""

    id = models.BigAutoField(primary_key=True)
    doctor1_id = models.CharField(max_length=20, db_index=True)
    doctor2_id = models.CharField(max_length=20, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_rooms"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor1_id", "doctor2_id"],
                name="unique_doctor_chat_room",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    doctor1_id__lt=models.F("doctor2_id")
                ),
                name="chat_doctor_order_check",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.doctor1_id and self.doctor2_id:
            doctor_ids = sorted([
                self.doctor1_id,
                self.doctor2_id,
            ])
            self.doctor1_id = doctor_ids[0]
            self.doctor2_id = doctor_ids[1]

        super().save(*args, **kwargs)

    def has_doctor(self, doctor_id):
        return doctor_id in [
            self.doctor1_id,
            self.doctor2_id,
        ]

    def get_other_doctor_id(self, doctor_id):
        if doctor_id == self.doctor1_id:
            return self.doctor2_id

        if doctor_id == self.doctor2_id:
            return self.doctor1_id

        return None

    def __str__(self):
        return (
            f"ChatRoom("
            f"{self.id}, "
            f"{self.doctor1_id}, "
            f"{self.doctor2_id}"
            f")"
        )


class ChatMessage(models.Model):
    """채팅 메시지 및 환자 관련 공유 자료."""

    class MessageType(models.TextChoices):
        TEXT = "text", "텍스트"
        PATIENT = "patient", "환자 자료"
        EXAMINATION = "examination", "검사 자료"
        AI_RESULT = "ai_result", "AI 분석 결과"
        CONSULTATION = "consultation", "협진 요청"

    class ResourceStatus(models.TextChoices):
        UNREAD = "unread", "안 읽음"
        CHECKED = "checked", "확인함"
        ANSWERED = "answered", "답변 완료"

    id = models.BigAutoField(primary_key=True)

    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    sender_id = models.CharField(max_length=20, db_index=True)
    receiver_id = models.CharField(max_length=20, db_index=True)

    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT,
        db_index=True,
    )
    content = models.TextField(blank=True, default="")

    patient_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
    )
    exam_id = models.IntegerField(null=True, blank=True)
    ai_result_id = models.IntegerField(null=True, blank=True)
    consultation_id = models.BigIntegerField(null=True, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    resource_status = models.CharField(
        max_length=20,
        choices=ResourceStatus.choices,
        default=ResourceStatus.UNREAD,
    )
    checked_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["room", "created_at"],
                name="chat_message_room_idx",
            ),
            models.Index(
                fields=["receiver_id", "is_read"],
                name="chat_receiver_read_idx",
            ),
        ]

    @property
    def has_shared_resource(self):
        return self.message_type != self.MessageType.TEXT

    def __str__(self):
        return (
            f"ChatMessage("
            f"{self.id}, "
            f"{self.sender_id} → "
            f"{self.receiver_id}"
            f")"
        )


class Memo(models.Model):
    class MemoType(models.TextChoices):
        TEXT = "text", "텍스트"
        VOICE = "voice", "음성"

    class TranscriptionStatus(models.TextChoices):
        NONE = "none", "없음"
        PROCESSING = "processing", "처리중"
        COMPLETED = "completed", "완료"
        FAILED = "failed", "실패"

    id = models.BigAutoField(primary_key=True)
    doctor_id = models.CharField(max_length=20, db_index=True)
    patient_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    exam_id = models.IntegerField(null=True, blank=True)
    memo_type = models.CharField(
        max_length=20,
        choices=MemoType.choices,
        default=MemoType.TEXT,
    )
    title = models.CharField(max_length=200, blank=True, default="")
    content = models.TextField(blank=True, default="")
    audio_file = models.FileField(
        upload_to="memos/audio/%Y/%m/%d/",
        null=True,
        blank=True,
    )
    audio_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    transcript = models.TextField(blank=True, default="")
    transcription_status = models.CharField(
        max_length=20,
        choices=TranscriptionStatus.choices,
        default=TranscriptionStatus.NONE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "memos"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Memo({self.id}, {self.doctor_id})"


class Notification(models.Model):
    id = models.BigAutoField(primary_key=True)
    recipient_doctor_id = models.CharField(max_length=20, db_index=True)
    notification_type = models.CharField(max_length=30, default="consultation")
    title = models.CharField(max_length=200)
    message = models.TextField()
    consultation_id = models.CharField(max_length=50, null=True, blank=True)

    chat_room_id = models.BigIntegerField(null=True, blank=True)
    chat_message_id = models.BigIntegerField(null=True, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification({self.id}, {self.recipient_doctor_id}, {self.title})"


class EMRSignOff(models.Model):
    id = models.BigAutoField(primary_key=True)
    patient_id = models.CharField(max_length=50, db_index=True)
    doctor_id = models.CharField(max_length=20, db_index=True)
    finalized = models.BooleanField(default=False)
    final_result = models.TextField(blank=True, default="")
    ai_result = models.JSONField(null=True, blank=True)
    emr_transmitted = models.BooleanField(default=False)
    transmitted_at = models.DateTimeField(null=True, blank=True)
    report_ready = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "emr_signoffs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"EMRSignOff({self.id}, {self.patient_id}, {self.doctor_id})"

class PatientAuth(models.Model):
    auth_id = models.BigAutoField(primary_key=True)

    patient_id = models.ForeignKey(
        Patient,
        db_column="patient_id",
        on_delete=models.CASCADE,)

    provider = models.CharField(max_length=20)

    provider_user_id = models.CharField(max_length=100)

    email = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField()

    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "patient_auth"
        managed = False

    def __str__(self):
        return f"{self.provider}:{self.provider_user_id}"
