from rest_framework import serializers
from api.models import Doctor, Patient, Examination, AIResult, Bookmark
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
            "troponin_t_level",
            "history_score",
            "risk_factors_count",
        ]


class PatientListItemSerializer(serializers.ModelSerializer):
    """목록/홈용: 환자 + 최근 AI 판정 요약"""

    latest_severity_class = serializers.SerializerMethodField()
    has_lesion = serializers.SerializerMethodField()

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
