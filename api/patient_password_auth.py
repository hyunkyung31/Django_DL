"""
Django_DL 에 적용할 환자 아이디/비밀번호 인증 API.

적용 위치 예:
  - api/serializers.py 에 serializer 추가
  - api/views.py 에 patient_login / patient_signup 추가
  - config/urls.py 에 라우트 등록

POST /api/auth/patient/signup/
  { name, phone, birthDate, password, username? }
  → 기존 patients(name+phone) 매칭 후에만 가입
  → patients.password 저장 + patient_auth(provider=password)

POST /api/auth/patient/login/
  { username, password }
  → username = 가입 시 아이디 또는 휴대폰번호
"""

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import Patient, PatientAuth


class PatientPasswordSignupSerializer(serializers.Serializer):
    name = serializers.CharField()
    phone = serializers.CharField()
    birthDate = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=4)
    # 앱 로그인 아이디 (필수). 휴대폰과 별개로 저장 → 둘 다로 로그인 가능
    username = serializers.CharField(min_length=3, max_length=50)


class PatientPasswordLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


def _digits_phone(raw: str) -> str:
    return "".join(ch for ch in (raw or "") if ch.isdigit())


def _issue_patient_tokens(patient: Patient):
    user, _ = User.objects.get_or_create(username=patient.patient_id)
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "patient_id": patient.patient_id,
        "patient_name": patient.patient_name,
        "is_new_user": False,
        "signup_token": None,
    }


def _password_matches(stored: str | None, raw: str) -> bool:
    if not stored:
        return False
    # 해시된 값이면 check_password, 레거시 평문이면 직접 비교
    if stored.startswith(("pbkdf2_", "argon2", "bcrypt$", "scrypt$")):
        return check_password(raw, stored)
    return stored == raw


@api_view(["POST"])
def patient_signup(request):
    """
    병원 등록 환자만 앱 회원가입.
    이름+전화번호로 patients 매칭 → password 계정 생성.
    """
    serializer = PatientPasswordSignupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    name = serializer.validated_data["name"].strip()
    phone = _digits_phone(serializer.validated_data["phone"])
    birth_date = serializer.validated_data["birthDate"].strip()
    password = serializer.validated_data["password"]
    username = serializer.validated_data["username"].strip()

    if not name:
        return Response({"message": "이름은 필수입니다."}, status=400)
    if not username or len(username) < 3:
        return Response(
            {"message": "아이디는 3자 이상이어야 합니다."},
            status=400,
        )
    if len(phone) != 11 or not phone.startswith("010"):
        return Response(
            {"message": "전화번호는 010으로 시작하는 11자리여야 합니다."},
            status=400,
        )
    if not birth_date:
        return Response({"message": "생년월일은 필수입니다."}, status=400)
    if len(password) < 4:
        return Response({"message": "비밀번호는 4자 이상이어야 합니다."}, status=400)

    # 병원 EMR에 등록된 환자만 (이름 + 전화 Exact)
    # ※ patients.phone_number 가 NULL 이면 매칭 실패 → Heidi 전에 전화 채워야 함
    matched = list(
        Patient.objects.filter(phone_number=phone, patient_name=name)[:2]
    )
    if len(matched) == 0:
        return Response(
            {
                "message": (
                    "일치하는 병원 환자 정보가 없습니다. "
                    "병원에 등록된 이름/연락처로 가입해주세요."
                )
            },
            status=404,
        )
    if len(matched) > 1:
        return Response(
            {"message": "일치하는 환자가 여러 명입니다. 병원에 문의해주세요."},
            status=400,
        )

    patient = matched[0]

    # 동일 아이디가 이미 있으면 불가
    if PatientAuth.objects.filter(
        provider="password",
        provider_user_id=username,
    ).exists():
        return Response(
            {"message": "이미 사용 중인 아이디입니다."},
            status=409,
        )

    # 이 환자로 이미 비밀번호 가입됨
    if PatientAuth.objects.filter(
        provider="password",
        patient_id=patient,
    ).exists():
        return Response(
            {"message": "이미 아이디/비밀번호로 가입된 환자입니다. 로그인해주세요."},
            status=409,
        )

    patient.password = make_password(password)
    patient.save(update_fields=["password"])

    PatientAuth.objects.create(
        patient_id=patient,
        provider="password",
        provider_user_id=username,
        email=None,
        created_at=timezone.now(),
        last_login=timezone.now(),
    )

    return Response(_issue_patient_tokens(patient), status=201)


@api_view(["POST"])
def patient_login(request):
    """아이디(또는 휴대폰) + 비밀번호 로그인."""
    serializer = PatientPasswordLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    username = serializer.validated_data["username"].strip()
    password = serializer.validated_data["password"]
    phone = _digits_phone(username)

    auth = PatientAuth.objects.filter(
        provider="password",
        provider_user_id=username,
    ).first()
    if auth is None and phone:
        auth = PatientAuth.objects.filter(
            provider="password",
            provider_user_id=phone,
        ).first()

    patient = None
    if auth is not None:
        patient = auth.patient_id
    else:
        # auth row 없이 patients.password 만 있는 레거시 대응
        qs = Patient.objects.filter(patient_id=username)
        if phone and not qs.exists():
            qs = Patient.objects.filter(phone_number=phone)
        patient = qs.first()

    if patient is None or not _password_matches(patient.password, password):
        return Response(
            {"detail": "아이디 또는 비밀번호가 올바르지 않습니다."},
            status=401,
        )

    if auth is not None:
        auth.last_login = timezone.now()
        auth.save(update_fields=["last_login"])

    return Response(_issue_patient_tokens(patient))


# urls.py 에 추가:
#   path("api/auth/patient/signup/", patient_signup),
#   path("api/auth/patient/login/", patient_login),
