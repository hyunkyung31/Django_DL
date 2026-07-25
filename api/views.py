import requests 
from django.conf import settings

from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema
from django.db.models import Q

from api.models import Doctor, Patient, Examination, AIResult
from api.serializers import (
    LoginSerializer,
    LoginResponseSerializer,
    PatientSerializer,
    PatientListResponseSerializer,
    ExaminationSerializer,
    AIResultSerializer,
    PatientDetailSerializer,
)

@api_view(['GET'])
def health_check(request) :
    return Response({"status" : "ok", "message" : "ANGIO CDSS 백엔드 서버가 정상 작동 중입니다."})

@extend_schema(
    request=LoginSerializer,
    responses={200: LoginResponseSerializer},
    tags=["auth"],
)

@api_view(["POST"])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    username = serializer.validated_data["username"]
    password = serializer.validated_data["password"]
    doctor = Doctor.objects.filter(doctor_id=username).first()
    if doctor is None or doctor.password != password:
        return Response(
            {"detail": "아이디 또는 비밀번호가 올바르지 않습니다."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    user, _ = User.objects.get_or_create(username=doctor.doctor_id)
    refresh = RefreshToken.for_user(user)
    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "doctor_id": doctor.doctor_id,
        "doctor_name": doctor.doctor_name,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
    })

@extend_schema(
    responses={200: PatientListResponseSerializer},
    tags=["patients"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_list(request):
    # 목록 = 내 담당 환자만
    doctor_id = request.user.username
    patients = (
        Patient.objects
        .filter(primary_doctor_id=doctor_id)
        .order_by("patient_id")
    )
    results = PatientSerializer(patients, many=True).data
    return Response({
        "doctor_id": doctor_id,
        "count": len(results),
        "results": results,
    })

@extend_schema(
    responses={200: PatientDetailSerializer},
    tags=["patients"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_detail(request, patient_id):
    # 상세 = 로그인한 의사면 어떤 환자든 조회 가능
    patient = Patient.objects.filter(patient_id=patient_id).first()
    if patient is None:
        return Response(
            {"detail": "환자를 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    exams = Examination.objects.filter(patient_id=patient_id).order_by("exam_id")
    exam_ids = [e.exam_id for e in exams]
    ai_results = AIResult.objects.filter(exam_id__in=exam_ids)
    return Response({
        "patient": PatientSerializer(patient).data,
        "examinations": ExaminationSerializer(exams, many=True).data,
        "ai_results": AIResultSerializer(ai_results, many=True).data,
    })

@extend_schema(
    responses={200: PatientListResponseSerializer},
    tags=["patients"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_search(request):
    """전체 환자에서 ID/이름 검색 (담당 제한 없음)"""
    q = (request.query_params.get("q") or "").strip()

    if not q:
        return Response(
            {"detail": "검색어 q를 입력해주세요."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    patients = Patient.objects.filter(
        Q(patient_id__icontains=q) | Q(patient_name__icontains=q)
    ).order_by("patient_id")[:50]

    results = PatientSerializer(patients, many=True).data
    return Response({
        "doctor_id": request.user.username,
        "count": len(results),
        "results": results,
        "query": q,
    })

def _forward_to_ai(endpoint: str, uploaded_file):
    """AI 서버로 이미지 파일 전달"""
    url = f"{settings.AI_SERVER_URL.rstrip('/')}{endpoint}"
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.read(),
            uploaded_file.content_type or "application/octet-stream",
        )
    }
    try:
        ai_response = requests.post(url, files=files, timeout=120)
    except requests.RequestException as exc:
        return Response(
            {"detail": f"AI 서버 연결 실패: {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    try:
        data = ai_response.json()
    except ValueError:
        data = {"detail": ai_response.text}

    return Response(data, status=ai_response.status_code)


@extend_schema(tags=["ai"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_predict(request):
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response(
            {"detail": "file 필드에 이미지를 업로드해주세요."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return _forward_to_ai("/inception/predict", uploaded)


@extend_schema(tags=["ai"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_gradcam(request):
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response(
            {"detail": "file 필드에 이미지를 업로드해주세요."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return _forward_to_ai("/inception/gradcam", uploaded)