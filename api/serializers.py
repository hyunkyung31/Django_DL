from rest_framework import serializers
from api.models import Doctor, Patient, Examination, AIResult, Bookmark, Consultation, Notification, EMRSignOff
from api.models import ChatRoom, ChatMessage
from api.models import Memo

import os
from django.conf import settings
from api.media_utils import build_media_url

def _normalize_ecg_type(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    mapping = {
        "Normal": "Normal",
        "Nonspecific": "Nonspecific",
        "ST_Depression": "ST_Depression",
        "정상": "Normal",
        "비특이": "Nonspecific",
        "비특이적": "Nonspecific",
        "ST하강": "ST_Depression",
        "ST 하강": "ST_Depression",
    }
    return mapping.get(raw)


def _build_ecg_image_url(request, patient) -> str | None:
    ecg_type = _normalize_ecg_type(getattr(patient, "ecg_result", None))
    if not request or not ecg_type:
        return None
    relative = f"ecg/{patient.patient_id}_{ecg_type}.png"
    full = os.path.join(settings.MEDIA_ROOT, "ecg", f"{patient.patient_id}_{ecg_type}.png")
    if not os.path.isfile(full):
        return None
    return build_media_url(request, relative)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    doctor_id = serializers.CharField()
    doctor_name = serializers.CharField()

class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = [
            "doctor_id",
            "doctor_name",
            "department",
            "hospital_name",
        ]


class PatientSerializer(serializers.ModelSerializer):
    ecg_image_url = serializers.SerializerMethodField()
    class Meta:
        model = Patient
        fields = [
            "patient_id",
            "patient_name",
            "gender",
            "age",
            "primary_doctor_id",
            "chief_complaint",
            "ecg_result",
            "ecg_image_url",
            "troponin_t_level",
            "history_score",
            "risk_factors_count",
        ]

    def get_ecg_image_url(self, obj):
        return _build_ecg_image_url(self.context.get("request"), obj)

class PatientListItemSerializer(serializers.ModelSerializer):
    """목록/홈용: 환자 + 최근 AI 판정 요약"""

    latest_severity_class = serializers.SerializerMethodField()
    has_lesion = serializers.SerializerMethodField()
    ecg_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "patient_id",
            "patient_name",
            "gender",
            "age",
            "primary_doctor_id",
            "chief_complaint",
            "ecg_result",
            "ecg_image_url",
            "troponin_t_level",
            "history_score",
            "risk_factors_count",
            "latest_severity_class",
            "has_lesion",
        ]

    def _latest_ai(self, obj):
        exam = (
            Examination.objects.filter(patient_id=obj.patient_id)
            .order_by("-exam_id")
            .first()
        )
        if not exam:
            return None
        return AIResult.objects.filter(exam_id=exam.exam_id).first()

    def get_latest_severity_class(self, obj):
        ai = self._latest_ai(obj)
        return ai.severity_class if ai else None

    def get_has_lesion(self, obj):
        ai = self._latest_ai(obj)
        if ai is None:
            return None
        return bool(ai.has_lesion)

    def get_ecg_image_url(self, obj):
        return _build_ecg_image_url(self.context.get("request"), obj)


class PatientListResponseSerializer(serializers.Serializer):
    doctor_id = serializers.CharField()
    count = serializers.IntegerField()
    results = PatientListItemSerializer(many=True)

class ExaminationSerializer(serializers.ModelSerializer):
    key_frame_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = Examination
        fields = [
            "exam_id",
            "patient_id",
            "vessel_type",
            "video_path",
            "key_frame_path",
            "key_frame_url",
            "video_url",
        ]

    def get_key_frame_url(self, obj):
        from api.media_utils import build_media_url

        request = self.context.get("request")
        if request is None:
            return None
        return build_media_url(request, obj.key_frame_path)

    def get_video_url(self, obj):
        from api.media_utils import build_media_url

        request = self.context.get("request")
        if request is None:
            return None
        return build_media_url(request, obj.video_path)

class AIResultSerializer(serializers.ModelSerializer):
    gradcam_url = serializers.SerializerMethodField()

    class Meta:
        model = AIResult
        fields = [
            "exam_id",
            "confirming_doctor_id",
            "has_lesion",
            "severity_class",
            "confidence_score",
            "ai_bbox_data",
            "gradcam_path",
            "gradcam_url",
            "heart_score",
            "mace_risk_percent",
            "doctor_opinion",
            "is_confirmed",
        ]

    def get_gradcam_url(self, obj):
        from api.media_utils import build_media_url

        request = self.context.get("request")
        if request is None:
            return None
        return build_media_url(request, obj.gradcam_path)

class PatientDetailSerializer(serializers.Serializer):
    patient = PatientSerializer()
    examinations = ExaminationSerializer(many=True)
    ai_results = AIResultSerializer(many=True)

class BookmarkSerializer(serializers.ModelSerializer):
    snapshot_url = serializers.SerializerMethodField()

    class Meta:
        model = Bookmark  # 위에서 from api.models import ... Bookmark 추가 필요
        fields = [
            "id",
            "doctor_id",
            "patient_id",
            "exam_id",
            "title",
            "note",
            "frame_number",
            "bbox_data",
            "snapshot_path",
            "snapshot_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "doctor_id", "created_at", "updated_at", "snapshot_url"]

    def get_snapshot_url(self, obj):
        from api.media_utils import build_media_url
        request = self.context.get("request")
        return build_media_url(request, obj.snapshot_path)


class ConsultationCreateSerializer(serializers.Serializer):
    patient_id = serializers.CharField(max_length=50)
    receiver_id = serializers.CharField(max_length=20)
    reason = serializers.CharField()
    priority = serializers.CharField(max_length=20, required=False, default="normal")
    memo = serializers.CharField(required=False, allow_blank=True, default="")
    reference_types = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
    )
    exam_id = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True, default=None)

    def to_internal_value(self, data):
        # 프론트 camelCase / snake_case 모두 허용
        data = data.copy() if hasattr(data, "copy") else dict(data)
        if "patientId" in data and "patient_id" not in data:
            data["patient_id"] = data.get("patientId")
        if "receiverId" in data and "receiver_id" not in data:
            data["receiver_id"] = data.get("receiverId")
        if "referenceTypes" in data and "reference_types" not in data:
            data["reference_types"] = data.get("referenceTypes")
        if "examId" in data and "exam_id" not in data:
            data["exam_id"] = data.get("examId")
        return super().to_internal_value(data)


class ConsultationSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    requester_name = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = [
            "id",
            "patient_id",
            "patient_name",
            "requester_id",
            "requester_name",
            "receiver_id",
            "receiver_name",
            "reason",
            "priority",
            "memo",
            "reference_types",
            "exam_id",
            "status",
            "is_read",
            "read_at",
            "reviewed_at",
            "response_memo",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_patient_name(self, obj):
        patient = Patient.objects.filter(
            patient_id=obj.patient_id,
        ).first()

        if patient is None:
            return ""

        return patient.patient_name

    def get_requester_name(self, obj):
        requester = Doctor.objects.filter(
            doctor_id=obj.requester_id,
        ).first()

        if requester is None:
            return ""

        return requester.doctor_name

    def get_receiver_name(self, obj):
        receiver = Doctor.objects.filter(
            doctor_id=obj.receiver_id,
        ).first()

        if receiver is None:
            return ""

        return receiver.doctor_name


class ConsultationStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultation
        fields = ["status"]

    def validate_status(self, new_status):
        current_status = self.instance.status

        allowed_transitions = {
            Consultation.Status.PENDING: {
                Consultation.Status.IN_PROGRESS,
            },
            Consultation.Status.IN_PROGRESS: {
                Consultation.Status.ACCEPTED,
                Consultation.Status.REJECTED,
            },
            Consultation.Status.ACCEPTED: {
                Consultation.Status.COMPLETED,
            },
        }

        allowed_statuses = allowed_transitions.get(
            current_status,
            set(),
        )

        if new_status not in allowed_statuses:
            raise serializers.ValidationError(
                f"{current_status} 상태에서 "
                f"{new_status} 상태로 변경할 수 없습니다."
            )

        return new_status


class NotificationSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="notification_type", read_only=True)
    consultation_id = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "title",
            "message",
            "consultation_id",
            "chat_room_id",
            "chat_message_id",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_consultation_id(self, obj):
        raw = obj.consultation_id
        if raw is None or raw == "":
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw



class EMRSignOffSerializer(serializers.ModelSerializer):
    class Meta:
        model = EMRSignOff
        fields = [
            "id",
            "patient_id",
            "doctor_id",
            "finalized",
            "final_result",
            "ai_result",
            "emr_transmitted",
            "transmitted_at",
            "report_ready",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "doctor_id", "created_at", "updated_at", "transmitted_at")

class KakaoLoginSerializer(serializers.Serializer) :
    accessToken = serializers.CharField()

class KakaoLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField(allow_blank=True)
    refresh = serializers.CharField(allow_blank=True)
    patient_id = serializers.CharField(required=False, allow_null=True)
    patient_name = serializers.CharField(required=False, allow_null=True)
    is_new_user = serializers.BooleanField()
    signup_token = serializers.CharField(required=False, allow_null=True, allow_blank=True)

class KakaoSignupSerializer(serializers.Serializer):
    signupToken = serializers.CharField()
    phone = serializers.CharField()
    birthDate = serializers.CharField()
    name = serializers.CharField()


class ConsultationReadSerializer(serializers.Serializer):
    is_read = serializers.BooleanField(
        required=False,
        default=True,
    )


class ConsultationResponseSerializer(serializers.Serializer):
    response_memo = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )

    def validate_response_memo(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "협진 소견을 입력해주세요."
            )

        return value


class ChatRoomCreateSerializer(serializers.Serializer):
    doctor_id = serializers.CharField(max_length=20)

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)

        if "doctorId" in data and "doctor_id" not in data:
            data["doctor_id"] = data.get("doctorId")

        return super().to_internal_value(data)


class ChatMessageCreateSerializer(serializers.Serializer):
    message_type = serializers.ChoiceField(
        choices=ChatMessage.MessageType.choices,
        required=False,
        default=ChatMessage.MessageType.TEXT,
    )
    content = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
    patient_id = serializers.CharField(
        max_length=50,
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
    )
    exam_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
    )
    ai_result_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
    )
    consultation_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
    )

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)

        camel_case_fields = {
            "messageType": "message_type",
            "patientId": "patient_id",
            "examId": "exam_id",
            "aiResultId": "ai_result_id",
            "consultationId": "consultation_id",
        }

        for camel_case, snake_case in camel_case_fields.items():
            if camel_case in data and snake_case not in data:
                data[snake_case] = data.get(camel_case)

        return super().to_internal_value(data)

    def validate(self, attrs):
        message_type = attrs.get(
            "message_type",
            ChatMessage.MessageType.TEXT,
        )
        content = (attrs.get("content") or "").strip()
        patient_id = attrs.get("patient_id")
        exam_id = attrs.get("exam_id")
        ai_result_id = attrs.get("ai_result_id")
        consultation_id = attrs.get("consultation_id")

        if (
            message_type == ChatMessage.MessageType.TEXT
            and not content
        ):
            raise serializers.ValidationError({
                "content": "메시지를 입력해주세요."
            })

        if (
            message_type
            in [
                ChatMessage.MessageType.PATIENT,
                ChatMessage.MessageType.EXAMINATION,
                ChatMessage.MessageType.AI_RESULT,
            ]
            and not patient_id
        ):
            raise serializers.ValidationError({
                "patient_id": (
                    "환자 자료 공유에는 "
                    "patient_id가 필요합니다."
                )
            })

        if (
            message_type
            == ChatMessage.MessageType.EXAMINATION
            and exam_id is None
        ):
            raise serializers.ValidationError({
                "exam_id": (
                    "검사 자료 공유에는 "
                    "exam_id가 필요합니다."
                )
            })

        if (
            message_type
            == ChatMessage.MessageType.AI_RESULT
            and ai_result_id is None
            and exam_id is None
        ):
            raise serializers.ValidationError({
                "ai_result_id": (
                    "AI 분석 결과 공유에는 "
                    "ai_result_id 또는 exam_id가 필요합니다."
                )
            })

        if (
            message_type
            == ChatMessage.MessageType.CONSULTATION
            and consultation_id is None
        ):
            raise serializers.ValidationError({
                "consultation_id": (
                    "협진 요청 공유에는 "
                    "consultation_id가 필요합니다."
                )
            })

        attrs["content"] = content
        attrs["patient_id"] = patient_id or None

        return attrs


class ChatMessageResourceStatusSerializer(serializers.Serializer):
    resource_status = serializers.ChoiceField(
        choices=[
            ChatMessage.ResourceStatus.CHECKED,
            ChatMessage.ResourceStatus.ANSWERED,
        ]
    )


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()
    patient = serializers.SerializerMethodField()
    examination = serializers.SerializerMethodField()
    ai_result = serializers.SerializerMethodField()
    consultation = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "room_id",
            "sender_id",
            "sender_name",
            "receiver_id",
            "receiver_name",
            "message_type",
            "content",
            "patient_id",
            "exam_id",
            "ai_result_id",
            "consultation_id",
            "patient",
            "examination",
            "ai_result",
            "consultation",
            "is_read",
            "read_at",
            "resource_status",
            "checked_at",
            "answered_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_sender_name(self, obj):
        doctor = Doctor.objects.filter(
            doctor_id=obj.sender_id,
        ).first()

        return doctor.doctor_name if doctor else ""

    def get_receiver_name(self, obj):
        doctor = Doctor.objects.filter(
            doctor_id=obj.receiver_id,
        ).first()

        return doctor.doctor_name if doctor else ""

    def get_patient(self, obj):
        if not obj.patient_id:
            return None

        patient = Patient.objects.filter(
            patient_id=obj.patient_id,
        ).first()

        if patient is None:
            return None

        return PatientSerializer(
            patient,
            context=self.context,
        ).data

    def get_examination(self, obj):
        if obj.exam_id is None:
            return None

        examination = Examination.objects.filter(
            exam_id=obj.exam_id,
        ).first()

        if examination is None:
            return None

        return ExaminationSerializer(
            examination,
            context=self.context,
        ).data

    def get_ai_result(self, obj):
        ai_result_id = (
            obj.ai_result_id
            if obj.ai_result_id is not None
            else obj.exam_id
        )

        if ai_result_id is None:
            return None

        ai_result = AIResult.objects.filter(
            exam_id=ai_result_id,
        ).first()

        if ai_result is None:
            return None

        return AIResultSerializer(
            ai_result,
            context=self.context,
        ).data

    def get_consultation(self, obj):
        if obj.consultation_id is None:
            return None

        consultation = Consultation.objects.filter(
            id=obj.consultation_id,
        ).first()

        if consultation is None:
            return None

        return ConsultationSerializer(
            consultation,
            context=self.context,
        ).data


class ChatRoomSerializer(serializers.ModelSerializer):
    other_doctor = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            "id",
            "doctor1_id",
            "doctor2_id",
            "other_doctor",
            "last_message",
            "unread_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _current_doctor_id(self):
        request = self.context.get("request")

        if request is None:
            return None

        return request.user.username

    def get_other_doctor(self, obj):
        current_doctor_id = self._current_doctor_id()

        if not current_doctor_id:
            return None

        other_doctor_id = obj.get_other_doctor_id(
            current_doctor_id
        )

        if not other_doctor_id:
            return None

        doctor = Doctor.objects.filter(
            doctor_id=other_doctor_id,
        ).first()

        if doctor is None:
            return None

        return DoctorSerializer(doctor).data

    def get_last_message(self, obj):
        message = obj.messages.order_by(
            "-created_at"
        ).first()

        if message is None:
            return None

        return ChatMessageSerializer(
            message,
            context=self.context,
        ).data

    def get_unread_count(self, obj):
        current_doctor_id = self._current_doctor_id()

        if not current_doctor_id:
            return 0

        return obj.messages.filter(
            receiver_id=current_doctor_id,
            is_read=False,
        ).count()


class MemoSerializer(serializers.ModelSerializer):
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = Memo
        fields = [
            "id",
            "doctor_id",
            "patient_id",
            "exam_id",
            "memo_type",
            "title",
            "content",
            "audio_url",
            "audio_duration_seconds",
            "transcript",
            "transcription_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "doctor_id",
            "audio_url",
            "transcript",
            "transcription_status",
            "created_at",
            "updated_at",
        ]

    def get_audio_url(self, obj):
        request = self.context.get("request")

        if request is None or not obj.audio_file:
            return None

        return request.build_absolute_uri(
            f"/api/memos/{obj.id}/audio/"
        )


class MemoCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Memo
        fields = [
            "patient_id",
            "exam_id",
            "memo_type",
            "title",
            "content",
            "audio_file",
            "audio_duration_seconds",
        ]

    def validate_audio_file(self, value):
        if value is None:
            return value

        allowed_types = {
            "audio/m4a",
            "audio/x-m4a",
            "audio/mp4",
            "audio/mpeg",
            "audio/wav",
            "audio/x-wav",
            "audio/aac",
            "audio/ogg",
            "audio/webm",
        }

        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                "지원하지 않는 음성 파일 형식입니다."
            )

        if value.size > 20 * 1024 * 1024:
            raise serializers.ValidationError(
                "음성 파일은 20MB 이하만 업로드할 수 있습니다."
            )

        return value

    def validate(self, attrs):
        memo_type = attrs.get(
            "memo_type",
            getattr(
                self.instance,
                "memo_type",
                Memo.MemoType.TEXT,
            ),
        )
        content = attrs.get(
            "content",
            getattr(self.instance, "content", ""),
        )
        audio_file = attrs.get(
            "audio_file",
            getattr(self.instance, "audio_file", None),
        )

        if (
            memo_type == Memo.MemoType.TEXT
            and not (content or "").strip()
        ):
            raise serializers.ValidationError({
                "content": "메모 내용을 입력해주세요."
            })

        if (
            memo_type == Memo.MemoType.VOICE
            and not audio_file
        ):
            raise serializers.ValidationError({
                "audio_file": "음성 파일을 첨부해주세요."
            })

        return attrs
