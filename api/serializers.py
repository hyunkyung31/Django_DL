from rest_framework import serializers
from api.models import Doctor, Patient, Examination, AIResult

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
        ]

class PatientListResponseSerializer(serializers.Serializer):
    doctor_id = serializers.CharField()
    count = serializers.IntegerField()
    results = PatientSerializer(many=True)

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
