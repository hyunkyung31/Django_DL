from api.models import ChatSession, ChatHistory


# ============================================
# Session
# ============================================

# 새 상담 시작
def create_session(patient_id, title="새로운 상담"):

    return ChatSession.objects.create(
        patient_id=patient_id,
        title=title
    )


def get_session(session_id):

    return ChatSession.objects.filter(
        id=session_id,
        is_active=True
    ).first()


# ============================================
# History 조회
# ============================================

def get_recent_history(
    session_id,
    limit=10
):

    history = ChatHistory.objects.filter(
        session_id=session_id
    ).order_by("-created_at")[:limit]

    return list(reversed(history))


# ============================================
# User Message 저장
# ============================================
# 사용자가 입력한 질문 저장
def save_user_message(
    session_id,
    message,
    intent="",
    risk_level=0,
    exam_id=None,
    ai_result_id=None,
    reference_type=ChatHistory.ReferenceType.GENERAL,
):

    return ChatHistory.objects.create(

        session_id=session_id,

        role=ChatHistory.Role.USER,

        content=message,

        intent=intent,

        risk_level=risk_level,

        exam_id=exam_id,

        ai_result_id=ai_result_id,

        reference_type=reference_type,
    )


# ============================================
# Assistant 저장
# ============================================
# GPT 답변 저장
def save_assistant_message(
    session_id,
    message,
    intent="",
    risk_level=0,
    exam_id=None,
    ai_result_id=None,
    reference_type=ChatHistory.ReferenceType.GENERAL,
):

    return ChatHistory.objects.create(

        session_id=session_id,

        role=ChatHistory.Role.ASSISTANT,

        content=message,

        intent=intent,

        risk_level=risk_level,

        exam_id=exam_id,

        ai_result_id=ai_result_id,

        reference_type=reference_type,
    )


# ============================================
# OpenAI Messages 생성
# ============================================

def build_history_messages(history):

    messages = []

    for chat in history:

        messages.append({

            "role": chat.role,

            "content": chat.content

        })

    return messages