import requests 
from django.conf import settings

from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import OpenApiResponse, extend_schema
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
    ChatRoom,
    ChatMessage,
    Memo,
    Appointment,
)
from api.ai_persist import AiPersistError, run_and_persist_exam_ai
from api.media_utils import (
    build_media_url,
    download_media_bytes,
    resolve_local_media_path,
    save_media_bytes,
    save_media_file,
)
from api.services.clinical_report_pdf import (
    ClinicalReportPdfError,
    generate_clinical_report_pdf,
)
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
    ConsultationStatusUpdateSerializer,
    NotificationSerializer,
    EMRSignOffSerializer,
    KakaoLoginSerializer,
    KakaoLoginResponseSerializer,
    KakaoSignupSerializer,
    ConsultationReadSerializer,
    ConsultationResponseSerializer,
    ChatRoomCreateSerializer,
    ChatRoomSerializer,
    ChatMessageCreateSerializer,
    ChatMessageSerializer,
    ChatMessageResourceStatusSerializer,
    MemoSerializer,
    MemoCreateUpdateSerializer,
    AppointmentCreateSerializer,
    AppointmentSerializer,
    AppointmentUpdateSerializer,
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


@extend_schema(
    methods=["GET"],
    responses={200: ConsultationSerializer(many=True)},
    tags=["consultations"],
)
@extend_schema(
    methods=["POST"],
    request=ConsultationCreateSerializer,
    responses={201: ConsultationSerializer},
    tags=["consultations"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def consultation_list(request):
    doctor_id = request.user.username

    if request.method == "GET":
        box = (
            request.query_params.get("box")
            or ""
        ).strip().lower()

        receiver = (
            request.query_params.get("receiver")
            or ""
        ).strip().lower()

        sender = (
            request.query_params.get("sender")
            or ""
        ).strip().lower()

        requested_status = (
            request.query_params.get("status")
            or ""
        ).strip().lower()

        if box == "received" or receiver == "me":
            queryset = Consultation.objects.filter(
                receiver_id=doctor_id,
            )
        elif box == "sent" or sender == "me":
            queryset = Consultation.objects.filter(
                requester_id=doctor_id,
            )
        else:
            queryset = Consultation.objects.filter(
                Q(requester_id=doctor_id)
                | Q(receiver_id=doctor_id)
            )

        if requested_status:
            valid_statuses = {
                value
                for value, _ in Consultation.Status.choices
            }

            if requested_status not in valid_statuses:
                return Response(
                    {
                        "detail": (
                            "올바르지 않은 협진 상태입니다."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = queryset.filter(
                status=requested_status,
            )

        queryset = queryset.order_by("-created_at")

        serializer = ConsultationSerializer(
            queryset,
            many=True,
            context={"request": request},
        )

        return Response({
            "doctor_id": doctor_id,
            "count": queryset.count(),
            "results": serializer.data,
        })

    serializer = ConsultationCreateSerializer(
        data=request.data,
    )
    serializer.is_valid(raise_exception=True)

    patient_id = serializer.validated_data[
        "patient_id"
    ]
    receiver_id = serializer.validated_data[
        "receiver_id"
    ]
    reason = serializer.validated_data["reason"]

    priority = (
        serializer.validated_data.get("priority")
        or "normal"
    )

    memo = (
        serializer.validated_data.get("memo")
        or ""
    )

    reference_types = (
        serializer.validated_data.get(
            "reference_types"
        )
        or []
    )

    exam_id = (
        serializer.validated_data.get("exam_id")
        or None
    )

    patient = Patient.objects.filter(
        patient_id=patient_id,
    ).first()

    if patient is None:
        return Response(
            {"detail": "환자를 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )

    receiver = Doctor.objects.filter(
        doctor_id=receiver_id,
    ).first()

    if receiver is None:
        return Response(
            {"detail": "수신 의사를 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if receiver_id == doctor_id:
        return Response(
            {
                "detail": (
                    "본인에게는 협진을 요청할 수 없습니다."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        consultation = Consultation.objects.create(
            patient_id=patient_id,
            requester_id=doctor_id,
            receiver_id=receiver_id,
            reason=reason,
            priority=priority,
            memo=memo,
            reference_types=reference_types,
            exam_id=exam_id,
            status=Consultation.Status.PENDING,
        )

        patient_label = (
            f"{patient.patient_name} "
            f"({patient.patient_id})"
        )

        Notification.objects.create(
            recipient_doctor_id=receiver_id,
            notification_type=(
                "consultation_created"
            ),
            title="새 협진 요청",
            message=(
                f"{patient_label} 환자의 "
                "새 협진 요청이 도착했습니다."
            ),
            consultation_id=str(consultation.id),
            is_read=False,
        )

    return Response(
        ConsultationSerializer(
            consultation,
            context={"request": request},
        ).data,
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    responses={200: ConsultationSerializer},
    tags=["consultations"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def consultation_detail(
    request,
    consultation_id,
):
    doctor_id = request.user.username

    consultation = Consultation.objects.filter(
        id=consultation_id,
    ).first()

    if consultation is None:
        return Response(
            {
                "detail": (
                    "협진 요청을 찾을 수 없습니다."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if doctor_id not in {
        consultation.requester_id,
        consultation.receiver_id,
    }:
        return Response(
            {
                "detail": (
                    "이 협진 요청을 조회할 "
                    "권한이 없습니다."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response(
        ConsultationSerializer(
            consultation,
            context={"request": request},
        ).data,
    )


CONSULTATION_STATUS_MESSAGES = {
    Consultation.Status.IN_PROGRESS: {
        "type": "consultation_in_progress",
        "title": "협진 검토가 시작되었습니다.",
        "message": (
            "수신 의료진이 협진 요청을 "
            "검토하고 있습니다."
        ),
    },
    Consultation.Status.ACCEPTED: {
        "type": "consultation_accepted",
        "title": "협진 요청이 수락되었습니다.",
        "message": (
            "수신 의료진이 협진 요청을 "
            "수락했습니다."
        ),
    },
    Consultation.Status.REJECTED: {
        "type": "consultation_rejected",
        "title": "협진 요청이 거절되었습니다.",
        "message": (
            "수신 의료진이 협진 요청을 "
            "거절했습니다."
        ),
    },
    Consultation.Status.COMPLETED: {
        "type": "consultation_completed",
        "title": "협진이 완료되었습니다.",
        "message": (
            "요청한 협진 처리가 완료되었습니다."
        ),
    },
}


@extend_schema(
    request=ConsultationStatusUpdateSerializer,
    responses={200: ConsultationSerializer},
    tags=["consultations"],
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def consultation_status_update(
    request,
    consultation_id,
):
    doctor_id = request.user.username

    with transaction.atomic():
        consultation = (
            Consultation.objects
            .select_for_update()
            .filter(id=consultation_id)
            .first()
        )

        if consultation is None:
            return Response(
                {
                    "detail": (
                        "협진 요청을 찾을 수 없습니다."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if consultation.receiver_id != doctor_id:
            return Response(
                {
                    "detail": (
                        "협진 요청을 받은 의료진만 "
                        "상태를 변경할 수 있습니다."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = (
            ConsultationStatusUpdateSerializer(
                consultation,
                data=request.data,
                partial=True,
            )
        )
        serializer.is_valid(raise_exception=True)

        consultation = serializer.save()

        notification_data = (
            CONSULTATION_STATUS_MESSAGES.get(
                consultation.status,
            )
        )

        if notification_data is not None:
            Notification.objects.create(
                recipient_doctor_id=(
                    consultation.requester_id
                ),
                notification_type=(
                    notification_data["type"]
                ),
                title=notification_data["title"],
                message=(
                    notification_data["message"]
                ),
                consultation_id=str(
                    consultation.id
                ),
                is_read=False,
            )

    return Response(
        ConsultationSerializer(
            consultation,
            context={"request": request},
        ).data,
    )


@extend_schema(
    responses={
        200: NotificationSerializer(many=True),
    },
    tags=["notifications"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_list(request):
    doctor_id = request.user.username

    queryset = Notification.objects.filter(
        recipient_doctor_id=doctor_id,
    ).order_by("-created_at")

    unread_only = (
        request.query_params.get("unread")
        or ""
    ).strip().lower()

    if unread_only in ("1", "true", "yes"):
        queryset = queryset.filter(
            is_read=False,
        )

    serializer = NotificationSerializer(
        queryset,
        many=True,
    )

    return Response({
        "count": queryset.count(),
        "unread_count": queryset.filter(
            is_read=False,
        ).count(),
        "results": serializer.data,
    })


@extend_schema(
    responses={200: NotificationSerializer},
    tags=["notifications"],
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def notification_mark_read(
    request,
    notification_id,
):
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

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(
            update_fields=["is_read", "read_at"],
        )

    return Response(
        NotificationSerializer(notification).data,
    )

@extend_schema(request=ConsultationReadSerializer, responses={200: ConsultationSerializer}, tags=["consultations"])
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def consultation_mark_read(request, consultation_id):
    doctor_id = request.user.username
    consultation = Consultation.objects.filter(id=consultation_id).first()
    if consultation is None:
        return Response({"detail": "협진 요청을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    if consultation.receiver_id != doctor_id:
        return Response({"detail": "협진 요청을 받은 의료진만 읽음 처리할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)
    serializer = ConsultationReadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    consultation.is_read = serializer.validated_data["is_read"]
    consultation.read_at = timezone.now() if consultation.is_read else None
    consultation.save(update_fields=["is_read", "read_at", "updated_at"])
    return Response(ConsultationSerializer(consultation, context={"request": request}).data)


@extend_schema(request=ConsultationResponseSerializer, responses={200: ConsultationSerializer}, tags=["consultations"])
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def consultation_complete(request, consultation_id):
    doctor_id = request.user.username
    with transaction.atomic():
        consultation = Consultation.objects.select_for_update().filter(id=consultation_id).first()
        if consultation is None:
            return Response({"detail": "협진 요청을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        if consultation.receiver_id != doctor_id:
            return Response({"detail": "협진 요청을 받은 의료진만 소견을 작성할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)
        if consultation.status not in {Consultation.Status.IN_PROGRESS, Consultation.Status.ACCEPTED}:
            return Response({"detail": "검토중 또는 수락된 협진만 답변 완료할 수 있습니다."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ConsultationResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        consultation.response_memo = serializer.validated_data["response_memo"]
        consultation.status = Consultation.Status.COMPLETED
        consultation.completed_at = now
        consultation.is_read = True
        consultation.read_at = consultation.read_at or now
        consultation.reviewed_at = consultation.reviewed_at or now
        consultation.save(update_fields=["response_memo", "status", "completed_at", "is_read", "read_at", "reviewed_at", "updated_at"])
        Notification.objects.create(
            recipient_doctor_id=consultation.requester_id,
            notification_type="consultation_completed",
            title="협진 소견이 도착했습니다.",
            message=f"{consultation.patient_id} 환자의 협진 소견 작성이 완료되었습니다.",
            consultation_id=str(consultation.id),
            is_read=False,
        )
    return Response(ConsultationSerializer(consultation, context={"request": request}).data)


@extend_schema(methods=["GET"], responses={200: ChatRoomSerializer(many=True)}, tags=["chat"])
@extend_schema(methods=["POST"], request=ChatRoomCreateSerializer, responses={201: ChatRoomSerializer}, tags=["chat"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def chat_room_list_create(request):
    doctor_id = request.user.username
    if request.method == "GET":
        queryset = ChatRoom.objects.filter(Q(doctor1_id=doctor_id) | Q(doctor2_id=doctor_id)).order_by("-updated_at")
        serializer = ChatRoomSerializer(queryset, many=True, context={"request": request})
        return Response({"count": queryset.count(), "results": serializer.data})
    serializer = ChatRoomCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    other_doctor_id = serializer.validated_data["doctor_id"]
    if other_doctor_id == doctor_id:
        return Response({"detail": "본인과 채팅방을 만들 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
    if not Doctor.objects.filter(doctor_id=other_doctor_id).exists():
        return Response({"detail": "의사를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    doctor_ids = sorted([doctor_id, other_doctor_id])
    room, created = ChatRoom.objects.get_or_create(doctor1_id=doctor_ids[0], doctor2_id=doctor_ids[1])
    return Response(
        ChatRoomSerializer(room, context={"request": request}).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(methods=["GET"], responses={200: ChatMessageSerializer(many=True)}, tags=["chat"])
@extend_schema(methods=["POST"], request=ChatMessageCreateSerializer, responses={201: ChatMessageSerializer}, tags=["chat"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def chat_message_list_create(request, room_id):
    doctor_id = request.user.username
    room = ChatRoom.objects.filter(id=room_id).first()
    if room is None:
        return Response({"detail": "채팅방을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    if not room.has_doctor(doctor_id):
        return Response({"detail": "이 채팅방에 접근할 권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
    if request.method == "GET":
        queryset = room.messages.order_by("created_at")
        serializer = ChatMessageSerializer(queryset, many=True, context={"request": request})
        return Response({"room_id": room.id, "count": queryset.count(), "results": serializer.data})
    serializer = ChatMessageCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    patient_id = data.get("patient_id")
    exam_id = data.get("exam_id")
    ai_result_id = data.get("ai_result_id")
    consultation_id = data.get("consultation_id")
    if patient_id and not Patient.objects.filter(patient_id=patient_id).exists():
        return Response({"detail": "공유할 환자를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    examination = Examination.objects.filter(exam_id=exam_id).first() if exam_id is not None else None
    if exam_id is not None and examination is None:
        return Response({"detail": "공유할 검사 자료를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    if examination is not None and patient_id and examination.patient_id != patient_id:
        return Response({"detail": "선택한 환자와 검사 자료가 일치하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
    if data["message_type"] == ChatMessage.MessageType.AI_RESULT:
        lookup_id = ai_result_id if ai_result_id is not None else exam_id
        if not AIResult.objects.filter(exam_id=lookup_id).exists():
            return Response({"detail": "공유할 AI 분석 결과를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    if consultation_id is not None:
        consultation = Consultation.objects.filter(id=consultation_id).first()
        if consultation is None:
            return Response({"detail": "공유할 협진 요청을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        if doctor_id not in {consultation.requester_id, consultation.receiver_id}:
            return Response({"detail": "이 협진 요청을 공유할 권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
    receiver_id = room.get_other_doctor_id(doctor_id)
    with transaction.atomic():
        message = ChatMessage.objects.create(
            room=room,
            sender_id=doctor_id,
            receiver_id=receiver_id,
            message_type=data["message_type"],
            content=data.get("content") or "",
            patient_id=patient_id,
            exam_id=exam_id,
            ai_result_id=ai_result_id,
            consultation_id=consultation_id,
            is_read=False,
            resource_status=ChatMessage.ResourceStatus.UNREAD,
        )
        room.updated_at = timezone.now()
        room.save(update_fields=["updated_at"])
        is_text = message.message_type == ChatMessage.MessageType.TEXT
        Notification.objects.create(
            recipient_doctor_id=receiver_id,
            notification_type="chat_message" if is_text else "shared_resource",
            title="새 채팅 메시지" if is_text else "새 공유 자료",
            message=message.content or "새로운 자료가 공유되었습니다.",
            chat_room_id=room.id,
            chat_message_id=message.id,
            is_read=False,
        )
    return Response(ChatMessageSerializer(message, context={"request": request}).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["chat"])
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def chat_room_mark_read(request, room_id):
    doctor_id = request.user.username
    room = ChatRoom.objects.filter(id=room_id).first()
    if room is None:
        return Response({"detail": "채팅방을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    if not room.has_doctor(doctor_id):
        return Response({"detail": "이 채팅방에 접근할 권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
    now = timezone.now()
    updated_count = ChatMessage.objects.filter(room=room, receiver_id=doctor_id, is_read=False).update(is_read=True, read_at=now)
    Notification.objects.filter(recipient_doctor_id=doctor_id, chat_room_id=room.id, is_read=False).update(is_read=True, read_at=now)
    return Response({"room_id": room.id, "updated_count": updated_count, "read_at": now})


@extend_schema(request=ChatMessageResourceStatusSerializer, responses={200: ChatMessageSerializer}, tags=["chat"])
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def chat_message_resource_status(request, message_id):
    doctor_id = request.user.username
    with transaction.atomic():
        message = ChatMessage.objects.select_for_update().filter(id=message_id).first()
        if message is None:
            return Response({"detail": "메시지를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        if message.receiver_id != doctor_id:
            return Response({"detail": "공유 자료를 받은 의료진만 상태를 변경할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)
        if not message.has_shared_resource:
            return Response({"detail": "일반 텍스트 메시지에는 자료 상태가 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ChatMessageResourceStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["resource_status"]
        if message.resource_status == ChatMessage.ResourceStatus.ANSWERED:
            return Response({"detail": "답변 완료된 자료 상태는 변경할 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        message.resource_status = new_status
        message.is_read = True
        message.read_at = message.read_at or now
        if new_status == ChatMessage.ResourceStatus.CHECKED:
            message.checked_at = now
        if new_status == ChatMessage.ResourceStatus.ANSWERED:
            message.checked_at = message.checked_at or now
            message.answered_at = now
        message.save(update_fields=["resource_status", "is_read", "read_at", "checked_at", "answered_at"])
    return Response(ChatMessageSerializer(message, context={"request": request}).data)


@extend_schema(methods=["GET"], responses={200: MemoSerializer(many=True)}, tags=["memos"])
@extend_schema(methods=["POST"], request=MemoCreateUpdateSerializer, responses={201: MemoSerializer}, tags=["memos"])
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def memo_list_create(request):
    doctor_id = request.user.username
    if request.method == "GET":
        queryset = Memo.objects.filter(doctor_id=doctor_id)
        patient_id = (request.query_params.get("patient_id") or "").strip()
        exam_id = (request.query_params.get("exam_id") or "").strip()
        memo_type = (request.query_params.get("memo_type") or "").strip()
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        if exam_id:
            try:
                queryset = queryset.filter(exam_id=int(exam_id))
            except ValueError:
                return Response({"detail": "exam_id가 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
        if memo_type:
            if memo_type not in Memo.MemoType.values:
                return Response({"detail": "memo_type이 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.filter(memo_type=memo_type)
        serializer = MemoSerializer(queryset, many=True, context={"request": request})
        return Response({"count": queryset.count(), "results": serializer.data})
    serializer = MemoCreateUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    patient_id = serializer.validated_data.get("patient_id")
    exam_id = serializer.validated_data.get("exam_id")
    error_response = _validate_memo_relations(patient_id, exam_id)
    if error_response:
        return error_response
    memo = serializer.save(doctor_id=doctor_id)
    return Response(MemoSerializer(memo, context={"request": request}).data, status=status.HTTP_201_CREATED)


@extend_schema(request=MemoCreateUpdateSerializer, responses={200: MemoSerializer}, tags=["memos"])
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def memo_detail(request, memo_id):
    doctor_id = request.user.username
    memo = Memo.objects.filter(id=memo_id, doctor_id=doctor_id).first()
    if memo is None:
        return Response({"detail": "메모를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        return Response(MemoSerializer(memo, context={"request": request}).data)
    if request.method == "DELETE":
        if memo.audio_file:
            memo.audio_file.delete(save=False)
        memo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = MemoCreateUpdateSerializer(memo, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    patient_id = serializer.validated_data.get("patient_id", memo.patient_id)
    exam_id = serializer.validated_data.get("exam_id", memo.exam_id)
    error_response = _validate_memo_relations(patient_id, exam_id)
    if error_response:
        return error_response
    old_audio_name = memo.audio_file.name if memo.audio_file else None
    memo = serializer.save()
    if old_audio_name and "audio_file" in serializer.validated_data and old_audio_name != memo.audio_file.name:
        memo.audio_file.storage.delete(old_audio_name)
    return Response(MemoSerializer(memo, context={"request": request}).data)


@extend_schema(request=MemoCreateUpdateSerializer, responses={201: MemoSerializer}, tags=["memos"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def voice_memo_create(request):
    data = request.data.copy()
    data["memo_type"] = Memo.MemoType.VOICE
    serializer = MemoCreateUpdateSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    patient_id = serializer.validated_data.get("patient_id")
    exam_id = serializer.validated_data.get("exam_id")
    error_response = _validate_memo_relations(patient_id, exam_id)
    if error_response:
        return error_response
    memo = serializer.save(doctor_id=request.user.username, memo_type=Memo.MemoType.VOICE)
    return Response(MemoSerializer(memo, context={"request": request}).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["memos"])
@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def memo_audio(request, memo_id):
    memo = Memo.objects.filter(id=memo_id, doctor_id=request.user.username).first()
    if memo is None:
        return Response({"detail": "메모를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    if not memo.audio_file:
        return Response({"detail": "음성 파일이 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        memo.audio_file.delete(save=False)
        memo.audio_file = None
        memo.audio_duration_seconds = None
        memo.save(update_fields=["audio_file", "audio_duration_seconds", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
    try:
        return FileResponse(memo.audio_file.open("rb"), content_type="application/octet-stream")
    except FileNotFoundError:
        return Response({"detail": "음성 파일을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)


def _validate_memo_relations(patient_id, exam_id):
    if patient_id and not Patient.objects.filter(patient_id=patient_id).exists():
        return Response({"detail": "환자를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    if exam_id is not None:
        examination = Examination.objects.filter(exam_id=exam_id).first()
        if examination is None:
            return Response({"detail": "검사 기록을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        if patient_id and examination.patient_id != patient_id:
            return Response({"detail": "환자와 검사 기록이 일치하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
    return None


class EMRSignOffListCreateView(generics.ListCreateAPIView):
    serializer_class = EMRSignOffSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EMRSignOff.objects.filter(
            doctor_id=self.request.user.username,
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(
            doctor_id=self.request.user.username,
        )


class EMRSignOffDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = EMRSignOffSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EMRSignOff.objects.filter(
            doctor_id=self.request.user.username,
        )

def _get_owned_emr_signoff(request, pk):
    return EMRSignOff.objects.filter(
        pk=pk,
        doctor_id=request.user.username,
    ).first()


@extend_schema(
    methods=["GET"],
    responses={
        200: OpenApiResponse(
            description="생성된 임상 보고서 PDF 파일",
        ),
        404: OpenApiResponse(
            description="보고서 또는 소견을 찾을 수 없음",
        ),
    },
    tags=["emr"],
)
@extend_schema(
    methods=["POST"],
    request=None,
    responses={
        200: EMRSignOffSerializer,
        400: OpenApiResponse(
            description="보고서 생성 조건을 충족하지 못함",
        ),
        404: OpenApiResponse(
            description="소견을 찾을 수 없음",
        ),
    },
    tags=["emr"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def emr_signoff_report(request, pk):
    signoff = _get_owned_emr_signoff(
        request,
        pk,
    )

    if signoff is None:
        return Response(
            {"detail": "임상 소견을 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        if not signoff.report_ready or not signoff.report_path:
            return Response(
                {"detail": "생성된 임상 보고서가 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            content, _, content_type = download_media_bytes(
                signoff.report_path,
            )
        except FileNotFoundError:
            return Response(
                {"detail": "저장된 임상 보고서 파일을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        filename = f"vena_clinical_report_{signoff.pk}.pdf"

        return FileResponse(
            io.BytesIO(content),
            as_attachment=True,
            filename=filename,
            content_type=content_type or "application/pdf",
        )

    if not signoff.finalized:
        return Response(
            {"detail": "최종 승인된 임상 소견만 보고서로 생성할 수 있습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not signoff.final_result.strip():
        return Response(
            {"detail": "최종 의료진 소견이 없습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not signoff.ai_result:
        return Response(
            {"detail": "저장된 AI 분석 결과가 없습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        pdf_content = generate_clinical_report_pdf(
            signoff,
        )
    except ClinicalReportPdfError as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    filename = f"clinical_report_{signoff.pk}.pdf"

    try:
        stored_path = save_media_bytes(
            patient_id=signoff.patient_id,
            media_type="reports",
            filename=filename,
            content=pdf_content,
            content_type="application/pdf",
        )
    except OSError:
        return Response(
            {"detail": "임상 보고서 파일 저장에 실패했습니다."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    generated_at = timezone.now()

    with transaction.atomic():
        locked_signoff = EMRSignOff.objects.select_for_update().filter(
            pk=signoff.pk,
            doctor_id=request.user.username,
        ).first()

        if locked_signoff is None:
            return Response(
                {"detail": "임상 소견을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        locked_signoff.report_path = stored_path
        locked_signoff.report_generated_at = generated_at
        locked_signoff.report_ready = True
        locked_signoff.save(
            update_fields=[
                "report_path",
                "report_generated_at",
                "report_ready",
                "updated_at",
            ]
        )

    serializer = EMRSignOffSerializer(
        locked_signoff,
        context={"request": request},
    )

    return Response(
        serializer.data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=None,
    responses={
        200: EMRSignOffSerializer,
        400: OpenApiResponse(
            description="전달 조건을 충족하지 못함",
        ),
        404: OpenApiResponse(
            description="소견을 찾을 수 없음",
        ),
    },
    tags=["emr"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def emr_signoff_transmit(request, pk):
    with transaction.atomic():
        signoff = EMRSignOff.objects.select_for_update().filter(
            pk=pk,
            doctor_id=request.user.username,
        ).first()

        if signoff is None:
            return Response(
                {"detail": "임상 소견을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not signoff.finalized:
            return Response(
                {"detail": "최종 승인되지 않은 임상 소견입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not signoff.report_ready or not signoff.report_path:
            return Response(
                {"detail": "임상 보고서를 먼저 생성해야 합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not signoff.emr_transmitted:
            signoff.emr_transmitted = True
            signoff.transmitted_at = timezone.now()
            signoff.save(
                update_fields=[
                    "emr_transmitted",
                    "transmitted_at",
                    "updated_at",
                ]
            )

    serializer = EMRSignOffSerializer(
        signoff,
        context={"request": request},
    )

    return Response(
        serializer.data,
        status=status.HTTP_200_OK,
    )


def _resolve_actor(user):
    """JWT username이 doctor_id인지 patient_id인지 판별."""
    username = user.username
    if Doctor.objects.filter(doctor_id=username).exists():
        return "doctor", username
    if Patient.objects.filter(patient_id=username).exists():
        return "patient", username
    return None, username


def _appointment_visible_to(appointment, role, actor_id):
    if role == "patient":
        return appointment.patient_id == actor_id
    if role == "doctor":
        return appointment.doctor_id == actor_id
    return False


def _apply_appointment_filters(queryset, params):
    status_filter = (params.get("status") or "").strip().lower()
    if status_filter:
        valid = {value for value, _ in Appointment.Status.choices}
        if status_filter not in valid:
            return None, Response(
                {"detail": "올바르지 않은 예약 상태입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = queryset.filter(status=status_filter)

    date_filter = (params.get("date") or "").strip()
    if date_filter:
        queryset = queryset.filter(scheduled_at__date=date_filter)

    date_from = (params.get("from") or params.get("date_from") or "").strip()
    if date_from:
        queryset = queryset.filter(scheduled_at__date__gte=date_from)

    date_to = (params.get("to") or params.get("date_to") or "").strip()
    if date_to:
        queryset = queryset.filter(scheduled_at__date__lte=date_to)

    patient_id = (params.get("patient_id") or "").strip()
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)

    doctor_id = (params.get("doctor_id") or "").strip()
    if doctor_id:
        queryset = queryset.filter(doctor_id=doctor_id)

    department = (params.get("department") or "").strip()
    if department:
        queryset = queryset.filter(department=department)

    return queryset, None


@extend_schema(
    request=AppointmentCreateSerializer,
    responses={200: AppointmentSerializer(many=True), 201: AppointmentSerializer},
    tags=["appointments"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def appointment_list(request):
    """
    GET  : 의사 — 담당 예약 목록 (date/status 필터)
           환자 — 내 예약 목록
    POST : 환자 — 예약 신청 (status=requested)
    """
    role, actor_id = _resolve_actor(request.user)
    if role is None:
        return Response(
            {"detail": "환자 또는 의사 계정이 아닙니다."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        if role == "doctor":
            queryset = Appointment.objects.filter(doctor_id=actor_id)
        else:
            queryset = Appointment.objects.filter(patient_id=actor_id)

        queryset, error = _apply_appointment_filters(
            queryset, request.query_params
        )
        if error is not None:
            return error

        queryset = queryset.order_by("scheduled_at", "-created_at")
        serializer = AppointmentSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response({
            "role": role,
            "actor_id": actor_id,
            "count": queryset.count(),
            "results": serializer.data,
        })

    # POST — 환자만 신청
    if role != "patient":
        return Response(
            {"detail": "예약 신청은 환자만 가능합니다."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = AppointmentCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    patient = Patient.objects.filter(patient_id=actor_id).first()
    if patient is None:
        return Response(
            {"detail": "환자를 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )

    doctor_id = (serializer.validated_data.get("doctor_id") or "").strip()
    if not doctor_id:
        doctor_id = (patient.primary_doctor_id or "").strip()

    if not doctor_id:
        return Response(
            {
                "detail": (
                    "담당 의사가 없어 예약을 신청할 수 없습니다. "
                    "doctor_id를 지정해 주세요."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    doctor = Doctor.objects.filter(doctor_id=doctor_id).first()
    if doctor is None:
        return Response(
            {"detail": "의사를 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )

    department = serializer.validated_data["department"].strip()
    if not department:
        department = doctor.department or ""

    scheduled_at = serializer.validated_data["scheduled_at"]
    memo = serializer.validated_data.get("memo") or ""

    with transaction.atomic():
        appointment = Appointment.objects.create(
            patient_id=actor_id,
            doctor_id=doctor_id,
            department=department,
            scheduled_at=scheduled_at,
            status=Appointment.Status.REQUESTED,
            memo=memo,
        )
        patient_label = f"{patient.patient_name} ({patient.patient_id})"
        Notification.objects.create(
            recipient_doctor_id=doctor_id,
            notification_type="appointment_requested",
            title="새 진료 예약 신청",
            message=(
                f"{patient_label} 환자의 진료 예약 신청이 도착했습니다."
            ),
            consultation_id=None,
            is_read=False,
        )

    return Response(
        AppointmentSerializer(
            appointment, context={"request": request}
        ).data,
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    responses={200: AppointmentSerializer(many=True)},
    tags=["appointments"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def appointment_me(request):
    """환자 전용: 내 예약 목록. GET /api/appointments/ 와 동일 결과."""
    role, actor_id = _resolve_actor(request.user)
    if role != "patient":
        return Response(
            {"detail": "환자 계정으로만 조회할 수 있습니다."},
            status=status.HTTP_403_FORBIDDEN,
        )

    queryset = Appointment.objects.filter(patient_id=actor_id)
    queryset, error = _apply_appointment_filters(
        queryset, request.query_params
    )
    if error is not None:
        return error

    queryset = queryset.order_by("scheduled_at", "-created_at")
    serializer = AppointmentSerializer(
        queryset, many=True, context={"request": request}
    )
    return Response({
        "patient_id": actor_id,
        "count": queryset.count(),
        "results": serializer.data,
    })


@extend_schema(
    request=AppointmentUpdateSerializer,
    responses={200: AppointmentSerializer},
    tags=["appointments"],
)
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def appointment_detail(request, appointment_id):
    role, actor_id = _resolve_actor(request.user)
    if role is None:
        return Response(
            {"detail": "환자 또는 의사 계정이 아닙니다."},
            status=status.HTTP_403_FORBIDDEN,
        )

    appointment = Appointment.objects.filter(id=appointment_id).first()
    if appointment is None:
        return Response(
            {"detail": "예약을 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _appointment_visible_to(appointment, role, actor_id):
        return Response(
            {"detail": "이 예약을 조회할 권한이 없습니다."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        return Response(
            AppointmentSerializer(
                appointment, context={"request": request}
            ).data
        )

    serializer = AppointmentUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    if not data:
        return Response(
            {"detail": "변경할 필드가 없습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    current = appointment.status
    terminal = {
        Appointment.Status.CANCELLED,
        Appointment.Status.COMPLETED,
    }
    if current in terminal:
        return Response(
            {"detail": f"'{current}' 상태의 예약은 변경할 수 없습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_status = data.get("status")
    update_fields = ["updated_at"]

    if role == "patient":
        # 환자: 일정/메모/진료과 변경, 또는 취소만
        if "doctor_id" in data:
            return Response(
                {"detail": "환자는 담당 의사를 변경할 수 없습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if new_status is not None and new_status != Appointment.Status.CANCELLED:
            return Response(
                {"detail": "환자는 예약을 취소(cancelled)만 할 수 있습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_status == Appointment.Status.CANCELLED:
            appointment.status = Appointment.Status.CANCELLED
            update_fields.append("status")
        if "scheduled_at" in data:
            if current not in {
                Appointment.Status.REQUESTED,
                Appointment.Status.CONFIRMED,
            }:
                return Response(
                    {"detail": "현재 상태에서는 일정을 변경할 수 없습니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            appointment.scheduled_at = data["scheduled_at"]
            update_fields.append("scheduled_at")
            # 확정 후 변경 시 재신청 상태로
            if current == Appointment.Status.CONFIRMED and new_status is None:
                appointment.status = Appointment.Status.REQUESTED
                update_fields.append("status")
        if "memo" in data:
            appointment.memo = data["memo"]
            update_fields.append("memo")
        if "department" in data:
            appointment.department = data["department"].strip()
            update_fields.append("department")

    else:
        # 의사: 확정/완료/취소, 일정·메모·의사 재배정
        doctor_transitions = {
            Appointment.Status.REQUESTED: {
                Appointment.Status.CONFIRMED,
                Appointment.Status.CANCELLED,
            },
            Appointment.Status.CONFIRMED: {
                Appointment.Status.COMPLETED,
                Appointment.Status.CANCELLED,
            },
        }
        if new_status is not None:
            allowed = doctor_transitions.get(current, set())
            if new_status not in allowed:
                return Response(
                    {
                        "detail": (
                            f"'{current}' → '{new_status}' "
                            "상태 변경은 허용되지 않습니다."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            appointment.status = new_status
            update_fields.append("status")

        if "scheduled_at" in data:
            appointment.scheduled_at = data["scheduled_at"]
            update_fields.append("scheduled_at")
        if "memo" in data:
            appointment.memo = data["memo"]
            update_fields.append("memo")
        if "department" in data:
            appointment.department = data["department"].strip()
            update_fields.append("department")
        if "doctor_id" in data:
            next_doctor_id = data["doctor_id"].strip()
            if not Doctor.objects.filter(doctor_id=next_doctor_id).exists():
                return Response(
                    {"detail": "의사를 찾을 수 없습니다."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            appointment.doctor_id = next_doctor_id
            update_fields.append("doctor_id")

    appointment.save(update_fields=list(dict.fromkeys(update_fields)))
    return Response(
        AppointmentSerializer(
            appointment, context={"request": request}
        ).data
    )

