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
    class Meta:
        model = Examination
        fields = [
            "exam_id",
            "patient_id",
            "vessel_type",
            "video_path",
            "key_frame_path",
        ]
class AIResultSerializer(serializers.ModelSerializer):
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
            "heart_score",
            "mace_risk_percent",
            "doctor_opinion",
            "is_confirmed",
        ]
class PatientDetailSerializer(serializers.Serializer):
    patient = PatientSerializer()
    examinations = ExaminationSerializer(many=True)
    ai_results = AIResultSerializer(many=True)
