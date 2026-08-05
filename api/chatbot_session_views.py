"""환자 AI 챗봇 세션/히스토리 조회 API."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from api.models import ChatHistory, ChatSession, Doctor, Patient


def _resolve_patient_id(user):
    username = user.username
    if Patient.objects.filter(patient_id=username).exists():
        return username
    return None


def _session_title(session: ChatSession) -> str:
    if session.title and session.title.strip() and session.title != "새로운 상담":
        return session.title
    first_user = (
        ChatHistory.objects.filter(
            session_id=session.id,
            role=ChatHistory.Role.USER,
        )
        .order_by("created_at")
        .first()
    )
    if first_user and first_user.content.strip():
        text = first_user.content.strip().replace("\n", " ")
        return text[:40] + ("…" if len(text) > 40 else "")
    return session.title or "새로운 상담"


@extend_schema(tags=["chatbot"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chatbot_session_list(request):
    """
    GET /api/chatbot/sessions/
    로그인한 환자의 AI 상담 세션 목록 (최신순).
    query: ?limit=20
    """
    patient_id = _resolve_patient_id(request.user)
    if patient_id is None:
        # 의사 계정은 환자 챗봇 history 조회 불가
        if Doctor.objects.filter(doctor_id=request.user.username).exists():
            return Response(
                {"detail": "환자 계정으로만 조회할 수 있습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {"detail": "환자 계정이 아닙니다."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        limit = int(request.query_params.get("limit") or 20)
    except ValueError:
        limit = 20
    limit = max(1, min(limit, 50))

    sessions = (
        ChatSession.objects.filter(patient_id=patient_id, is_active=True)
        .order_by("-updated_at")[:limit]
    )

    results = []
    for session in sessions:
        last = (
            ChatHistory.objects.filter(session_id=session.id)
            .order_by("-created_at")
            .first()
        )
        results.append(
            {
                "id": session.id,
                "patient_id": session.patient_id,
                "title": _session_title(session),
                "is_active": session.is_active,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "last_message": last.content if last else "",
                "last_role": last.role if last else None,
            }
        )

    return Response(
        {
            "patient_id": patient_id,
            "count": len(results),
            "results": results,
        }
    )


@extend_schema(tags=["chatbot"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chatbot_session_detail(request, session_id: int):
    """
    GET /api/chatbot/sessions/<session_id>/
    세션 메타 + 메시지 전체.
    """
    patient_id = _resolve_patient_id(request.user)
    if patient_id is None:
        return Response(
            {"detail": "환자 계정으로만 조회할 수 있습니다."},
            status=status.HTTP_403_FORBIDDEN,
        )

    session = ChatSession.objects.filter(id=session_id).first()
    if session is None:
        return Response(
            {"detail": "상담 세션을 찾을 수 없습니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if session.patient_id != patient_id:
        return Response(
            {"detail": "이 상담을 조회할 권한이 없습니다."},
            status=status.HTTP_403_FORBIDDEN,
        )

    messages = (
        ChatHistory.objects.filter(session_id=session.id)
        .order_by("created_at", "id")
    )
    return Response(
        {
            "id": session.id,
            "patient_id": session.patient_id,
            "title": _session_title(session),
            "is_active": session.is_active,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "intent": m.intent,
                    "risk_level": m.risk_level,
                    "reference_type": m.reference_type,
                    "exam_id": m.exam_id,
                    "created_at": m.created_at,
                }
                for m in messages
            ],
        }
    )
