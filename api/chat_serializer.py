from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):

    patient_id = serializers.CharField()

    message = serializers.CharField()

    session_id = serializers.IntegerField(
        required=False,
        allow_null=True
    )

    exam_id = serializers.IntegerField(
        required=False,
        allow_null=True
    )