from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import Doctor, Patient

@api_view(['GET'])
def health_check(request) :
    return Response({"status" : "ok", "message" : "ANGIO CDSS 백엔드 서버가 정상 작동 중입니다."})

@api_view(["POST"])
def login(request):
    # React에서 보내는 아이디/비번
    username = request.data.get("username")
    password = request.data.get("password")
    if not username or not password:
        return Response(
            {"detail": "아이디와 비밀번호를 입력해주세요."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # MySQL doctors 테이블에서 의사 찾기
    doctor = Doctor.objects.filter(doctor_id=username).first()
    # 없거나 비밀번호가 다르면 실패
    # (지금 DB 값은 Django 해시가 아니라서 문자열 비교)
    if doctor is None or doctor.password != password:
        return Response(
            {"detail": "아이디 또는 비밀번호가 올바르지 않습니다."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    # JWT는 Django User가 필요해서, doctor_id로 User를 만들거나 가져옴
    user, _ = User.objects.get_or_create(username=doctor.doctor_id)
    # 토큰 발급
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

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_list(request):
    # 로그인한 의사 ID (예: DOC-001)
    doctor_id = request.user.username

    patients = (
        Patient.objects
        .filter(primary_doctor_id=doctor_id)
        .order_by("patient_id")
    )

    data = []
    for p in patients:
        data.append({
            "patient_id": p.patient_id,
            "patient_name": p.patient_name,
            "gender": p.gender,
            "age": p.age,
            "primary_doctor_id": p.primary_doctor_id,
            "chief_complaint": p.chief_complaint,
            "ecg_result": p.ecg_result,
        })

    return Response({
        "doctor_id": doctor_id,
        "count": len(data),
        "results": data,
    })