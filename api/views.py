import requests 
from django.conf import settings

from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema
from django.db.models import Q

from django.db import transaction
from django.db.models import Max
from django.http import FileResponse
from django.core import signing

from api.models import (
    Doctor,
    Patient,
    Examination,
    AIResult,
    Bookmark,
    Consultation,
    Notification,
    EMRSignOff,
    PatientAuth,
)
from api.ai_persist import AiPersistError, run_and_persist_exam_ai
from api.media_utils import build_media_url, resolve_local_media_path, save_media_file
from api.serializers import (
    LoginSerializer,
    LoginResponseSerializer,
    DoctorSerializer,
    PatientSerializer,
    PatientListItemSerializer,
    PatientListResponseSerializer,
    ExaminationSerializer,
    AIResultSerializer,
    PatientDetailSerializer,
    BookmarkSerializer,
    ConsultationCreateSerializer,
    ConsultationSerializer,
    NotificationSerializer,
    EMRSignOffSerializer,
    KakaoLoginSerializer,
    KakaoLoginResponseSerializer,
    KakaoSignupSerializer,
)

from django.utils import timezone
from django.http import FileResponse, Http404
from google.cloud import storage
import io

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

SIGNUP_TOKEN_SALT = "kakao-signup"
SIGNUP_TOKEN_MAX_AGE = 60 * 10  # 10분


@api_view(["POST"])
def kakao_login(request):
    serializer = KakaoLoginSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    access_token = serializer.validated_data["accessToken"]

    kakao_response = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=5,
    )

    if kakao_response.status_code != 200:
        return Response(
            {"message": "유효하지 않은 카카오 토큰입니다."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    kakao_user = kakao_response.json()
    kakao_id = str(kakao_user["id"])

    auth = PatientAuth.objects.filter(
        provider="kakao",
        provider_user_id=kakao_id,
    ).first()

    # 기존 회원
    if auth:
        patient = auth.patient_id  # FK 이름이 patient_id

        user, _ = User.objects.get_or_create(
            username=patient.patient_id,
        )

        refresh = RefreshToken.for_user(user)

        auth.last_login = timezone.now()
        auth.save(update_fields=["last_login"])

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "patient_id": patient.patient_id,
            "patient_name": patient.patient_name,
            "is_new_user": False,
            "signup_token": None,
        })

    # 신규 회원
    signer = signing.TimestampSigner(salt=SIGNUP_TOKEN_SALT)
    signup_token = signer.sign(kakao_id)

    return Response(
        {
            "is_new_user": True,
            "signup_token": signup_token,
            "access": "",
            "refresh": "",
            "patient_id": None,
            "patient_name": None,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def kakao_signup(request):
    """
    POST /api/auth/kakao/signup/
    body: {
      "signupToken": "...",
      "phone": "01012345678",
      "birthDate": "1990-01-01",
      "name": "홍길동"
    }
    """
    serializer = KakaoSignupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    signup_token = serializer.validated_data["signupToken"]
    name = serializer.validated_data["name"].strip()
    phone = "".join(
        ch for ch in serializer.validated_data["phone"] if ch.isdigit()
    )
    birth_date = serializer.validated_data["birthDate"].strip()

    if not name:
        return Response(
            {"message": "이름은 필수입니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(phone) != 11 or not phone.startswith("010"):
        return Response(
            {"message": "전화번호는 010으로 시작하는 11자리여야 합니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not birth_date:
        return Response(
            {"message": "생년월일은 필수입니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    signer = signing.TimestampSigner(salt=SIGNUP_TOKEN_SALT)
    try:
        kakao_id = signer.unsign(signup_token, max_age=SIGNUP_TOKEN_MAX_AGE)
    except signing.SignatureExpired:
        return Response(
            {"message": "signup_token이 만료되었습니다. 다시 로그인해주세요."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except signing.BadSignature:
        return Response(
            {"message": "유효하지 않은 signup_token입니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    auth = PatientAuth.objects.filter(
        provider="kakao",
        provider_user_id=kakao_id,
    ).first()
    if auth:
        patient = auth.patient_id
        user, _ = User.objects.get_or_create(username=patient.patient_id)
        refresh = RefreshToken.for_user(user)
        auth.last_login = timezone.now()
        auth.save(update_fields=["last_login"])
        return Response({
            "is_new_user": False,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "patient_id": patient.patient_id,
            "patient_name": patient.patient_name,
            "signup_token": None,
        })

    # 이름 + 전화번호로 매칭
    # TODO: Patient에 birth_date 컬럼 생기면 birth_date도 조건 추가
    qs = Patient.objects.filter(
        phone_number=phone,
        patient_name=name,
    )

    matched = list(qs[:2])
    if len(matched) == 0:
        return Response(
            {"message": "일치하는 환자 정보가 없습니다. 회원가입이 필요합니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if len(matched) > 1:
        return Response(
            {"message": "일치하는 환자가 여러 명입니다. 입력 정보를 다시 확인해주세요."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    patient = matched[0]

    already_linked = PatientAuth.objects.filter(
        provider="kakao",
        patient_id=patient,
    ).exclude(provider_user_id=kakao_id).exists()
    if already_linked:
        return Response(
            {"message": "이미 다른 카카오 계정과 연결된 환자입니다."},
            status=status.HTTP_409_CONFLICT,
        )

    PatientAuth.objects.create(
        patient_id=patient,
        provider="kakao",
        provider_user_id=kakao_id,
        email=None,
        created_at=timezone.now(),
        last_login=timezone.now(),
    )

    user, _ = User.objects.get_or_create(username=patient.patient_id)
    refresh = RefreshToken.for_user(user)

    return Response({
        "is_new_user": False,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "patient_id": patient.patient_id,
        "patient_name": patient.patient_name,
        "signup_token": None,
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
    responses={200: DoctorSerializer(many=True)},
    tags=["doctors"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def doctor_list(request):
    doctors = Doctor.objects.all().order_by("doctor_id")
    return Response(DoctorSerializer(doctors, many=True).data)


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
    results = PatientListItemSerializer(
        patients, many=True, context={"request": request}
    ).data
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
        "patient": PatientSerializer(patient, context={"request": request}).data,
        "examinations": ExaminationSerializer(
            exams, many=True, context={"request": request}
        ).data,
        "ai_results": AIResultSerializer(
            ai_results, many=True, context={"request": request}
        ).data,
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

    results = PatientListItemSerializer(
        patients, many=True, context={"request": request}
    ).data
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


@extend_schema(tags=["media"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def media_local(request):
    """로컬 MEDIA_ROOT 파일을 JWT 인증 후 스트리밍."""
    relative = (request.query_params.get("path") or "").strip()
    full = resolve_local_media_path(relative)
    if full is None:
        return Response({"detail": "파일을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    return FileResponse(open(full, "rb"), as_attachment=False)


@extend_schema(tags=["media"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def patient_media_upload(request, patient_id):
    """
    환자 미디어 업로드.
    form-data:
      - file: 이미지/영상
      - media_type: key_frame | video | gradcam  (기본 key_frame)
    """
    patient = Patient.objects.filter(patient_id=patient_id).first()
    if patient is None:
        return Response({"detail": "환자를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response(
            {"detail": "file 필드에 파일을 업로드해주세요."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    media_type = (request.data.get("media_type") or "key_frame").strip()
    if media_type not in ("key_frame", "video", "gradcam"):
        return Response(
            {"detail": "media_type은 key_frame, video, gradcam 중 하나여야 합니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    stored_path = save_media_file(patient_id, media_type, uploaded)

    exam = (
        Examination.objects.filter(patient_id=patient_id)
        .order_by("exam_id")
        .first()
    )
    if exam is None:
        next_id = (Examination.objects.aggregate(m=Max("exam_id")).get("m") or 0) + 1
        exam = Examination(
            exam_id=next_id,
            patient_id=patient_id,
            vessel_type="UNKNOWN",
            video_path="",
            key_frame_path="",
        )

    if media_type == "key_frame":
        exam.key_frame_path = stored_path
    elif media_type == "video":
        exam.video_path = stored_path
    exam.save()

    if media_type == "gradcam":
        ai = AIResult.objects.filter(exam_id=exam.exam_id).first()
        if ai is None:
            ai = AIResult(
                exam_id=exam.exam_id,
                has_lesion=False,
                severity_class="unknown",
                confidence_score=0.0,
                is_confirmed=False,
            )
        ai.gradcam_path = stored_path
        ai.save()

    return Response(
        {
            "patient_id": patient_id,
            "exam_id": exam.exam_id,
            "media_type": media_type,
            "stored_path": stored_path,
            "url": build_media_url(request, stored_path),
            "examination": ExaminationSerializer(
                exam, context={"request": request}
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def media_gcs(request):
    gs_uri = (request.query_params.get("path") or "").strip()
    if not gs_uri.startswith("gs://"):
        return Response({"detail": "invalid path"}, status=400)
    without = gs_uri[5:]
    bucket_name, _, blob_name = without.partition("/")
    if not bucket_name or not blob_name:
        return Response({"detail": "invalid gs uri"}, status=400)
    try:
        client = storage.Client(project=getattr(settings, "GCS_PROJECT", None) or None)
        blob = client.bucket(bucket_name).blob(blob_name)
        data = blob.download_as_bytes()
    except Exception:
        raise Http404("file not found")
    content_type = blob.content_type or "application/octet-stream"
    return FileResponse(io.BytesIO(data), content_type=content_type)


@extend_schema(tags=["ai"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_image_analyze(request):
    """팀원 min 브랜치: 이미지 통합 분석 (YOLO+GradCAM 등) → AI /analysis/image"""
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response(
            {"detail": "file 필드에 이미지를 업로드해주세요."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return _forward_to_ai("/analysis/image", uploaded)

@extend_schema(tags=["ai"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def exam_ai_run_and_persist(request, exam_id: int):
    """
    exam keyframe으로 best 모델 추론 후 결과를 영구 저장한다.

    - bbox → ai_results.ai_bbox_data (JSON)
    - Grad-CAM overlay → GCS/local patients/{id}/gradcam/ + ai_results.gradcam_path
    - 분류 결과 → has_lesion / severity_class / confidence_score
    """
    def _float_param(name: str, default: float) -> float:
        raw = request.data.get(name, request.query_params.get(name, default))
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    confidence_threshold = _float_param("confidence_threshold", 0.25)
    iou_threshold = _float_param("iou_threshold", 0.45)

    if not 0.0 <= confidence_threshold <= 1.0 or not 0.0 <= iou_threshold <= 1.0:
        return Response(
            {"detail": "confidence_threshold / iou_threshold는 0~1 범위여야 합니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = run_and_persist_exam_ai(
            exam_id=exam_id,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
        )
    except AiPersistError as exc:
        return Response({"detail": exc.message}, status=exc.status_code)

    result["gradcam_url"] = build_media_url(request, result.get("gradcam_path"))
    return Response(result, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def bookmark_list(request):
    doctor_id = request.user.username

    if request.method == "GET":
        qs = Bookmark.objects.filter(doctor_id=doctor_id).order_by("-updated_at")
        patient_id = (request.query_params.get("patient_id") or "").strip()
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        data = BookmarkSerializer(qs, many=True, context={"request": request}).data
        return Response({
            "doctor_id": doctor_id,
            "count": len(data),
            "results": data,
        })

    # POST
    ser = BookmarkSerializer(data=request.data, context={"request": request})
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    now = timezone.now()
    bookmark = Bookmark.objects.create(
        doctor_id=doctor_id,
        patient_id=ser.validated_data.get("patient_id"),
        exam_id=ser.validated_data.get("exam_id"),
        title=ser.validated_data["title"],
        note=ser.validated_data.get("note"),
        frame_number=ser.validated_data.get("frame_number"),
        bbox_data=ser.validated_data.get("bbox_data") or [],
        snapshot_path=ser.validated_data.get("snapshot_path"),
        created_at=now,
        updated_at=now,
    )
    out = BookmarkSerializer(bookmark, context={"request": request}).data
    return Response(out, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def bookmark_detail(request, bookmark_id):
    doctor_id = request.user.username
    bookmark = Bookmark.objects.filter(id=bookmark_id, doctor_id=doctor_id).first()
    if bookmark is None:
        return Response({"detail": "북마크를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(BookmarkSerializer(bookmark, context={"request": request}).data)

    if request.method == "DELETE":
        bookmark.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH — 최신본 덮어쓰기
    ser = BookmarkSerializer(
        bookmark, data=request.data, partial=True, context={"request": request}
    )
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    for field in ("patient_id", "exam_id", "title", "note", "frame_number", "bbox_data", "snapshot_path"):
        if field in ser.validated_data:
            setattr(bookmark, field, ser.validated_data[field])
    bookmark.updated_at = timezone.now()
    bookmark.save()

    return Response(BookmarkSerializer(bookmark, context={"request": request}).data)


@extend_schema(tags=["consultations"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def consultation_list(request):
    doctor_id = request.user.username

    if request.method == "GET":
        qs = Consultation.objects.filter(
            Q(requester_id=doctor_id) | Q(receiver_id=doctor_id)
        ).order_by("-created_at")
        data = ConsultationSerializer(qs, many=True).data
        return Response({
            "doctor_id": doctor_id,
            "count": len(data),
            "results": data,
        })

    ser = ConsultationCreateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    patient_id = ser.validated_data["patient_id"]
    receiver_id = ser.validated_data["receiver_id"]
    reason = ser.validated_data["reason"]

    if Patient.objects.filter(patient_id=patient_id).first() is None:
        return Response(
            {"detail": "환자를 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if Doctor.objects.filter(doctor_id=receiver_id).first() is None:
        return Response(
            {"detail": "수신 의사를 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if receiver_id == doctor_id:
        return Response(
            {"detail": "본인에게는 협진을 요청할 수 없습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        consultation = Consultation.objects.create(
            patient_id=patient_id,
            requester_id=doctor_id,
            receiver_id=receiver_id,
            reason=reason,
            status="pending",
        )
        patient = Patient.objects.filter(patient_id=consultation.patient_id).first()

        patient_label = (

            f"{patient.patient_name} ({consultation.patient_id})"

            if patient and getattr(patient, "patient_name", None)

            else consultation.patient_id

        )

        Notification.objects.create(

            recipient_doctor_id=consultation.receiver_id,

            notification_type="consultation",

            title="새 협진 요청",

            message=f"{patient_label} 환자의 새 협진 요청이 도착했습니다.",

            consultation_id=str(consultation.id),

            is_read=False,

        )

    return Response(
        ConsultationSerializer(consultation).data,
        status=status.HTTP_201_CREATED,
    )


@extend_schema(tags=["notifications"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_list(request):
    doctor_id = request.user.username
    qs = Notification.objects.filter(recipient_doctor_id=doctor_id).order_by("-created_at")
    unread_only = (request.query_params.get("unread") or "").strip().lower()
    if unread_only in ("1", "true", "yes"):
        qs = qs.filter(is_read=False)
    data = NotificationSerializer(qs, many=True).data
    return Response(data)


@extend_schema(tags=["notifications"])
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def notification_mark_read(request, notification_id):
    doctor_id = request.user.username
    notification = Notification.objects.filter(
        id=notification_id,
        recipient_doctor_id=doctor_id,
    ).first()
    if notification is None:
        return Response(
            {"detail": "알림을 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return Response(NotificationSerializer(notification).data)


class EMRSignOffListCreateView(generics.ListCreateAPIView):
    queryset = EMRSignOff.objects.all().order_by("-created_at")
    serializer_class = EMRSignOffSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        with transaction.atomic():
            obj = serializer.save(doctor_id=self.request.user.username)
            if obj.emr_transmitted and not obj.transmitted_at:
                obj.transmitted_at = timezone.now()
                obj.save(update_fields=["transmitted_at"])


class EMRSignOffDetailView(generics.RetrieveUpdateAPIView):
    queryset = EMRSignOff.objects.all()
    serializer_class = EMRSignOffSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        with transaction.atomic():
            obj = serializer.save()
            if obj.emr_transmitted and not obj.transmitted_at:
                obj.transmitted_at = timezone.now()
                obj.save(update_fields=["transmitted_at"])

