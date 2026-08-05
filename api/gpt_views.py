from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from api.chat_serializer import ChatRequestSerializer

from api.services.chatbot_service import chat

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)

class GPTTestView(APIView):

    def get(self, request):

        result = chat(
            patient_id="TEST001",
            message="가슴이 답답하고 운동하면 숨이 찹니다."
        )

        return Response(result)


@extend_schema(
    summary="AI 의료 챗봇",
    description="LLM 기반 심혈관 의료 상담",
    request=ChatRequestSerializer,
    responses={
        200: OpenApiResponse(
            description="챗봇 응답"
        )
    },
)
class ChatAPIView(APIView):

    @extend_schema(
        summary="AI 의료 챗봇",
        description="LLM 기반 심혈관 의료 상담",
        request=ChatRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="챗봇 응답"
            )
        },
    )
    def post(self, request):

        serializer = ChatRequestSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        patient_id = serializer.validated_data["patient_id"]

        message = serializer.validated_data["message"]

        session_id = serializer.validated_data.get(
            "session_id"
        )

        exam_id = serializer.validated_data.get(
            "exam_id"
        )

        result = chat(
            patient_id=patient_id,
            message=message,
            session_id=session_id,
            exam_id=exam_id,
        )

        return Response(
            result,
            status=status.HTTP_200_OK
        )