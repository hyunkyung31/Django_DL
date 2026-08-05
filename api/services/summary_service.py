from api.models import ConversationMemory


def get_summary(session_id):
    """
    저장된 Summary 반환
    """
    try:
        memory = ConversationMemory.objects.filter(
            session_id=session_id,
        ).first()
    except Exception:
        return ""

    if memory is None:
        return ""

    return memory.summary or ""


def save_summary(
    session_id,
    summary,
):
    """
    Summary 저장
    """
    try:
        memory = ConversationMemory.objects.filter(
            session_id=session_id,
        ).first()

        if memory is None:
            memory = ConversationMemory(
                session_id=session_id,
            )

        memory.summary = summary
        memory.save()
    except Exception:
        # unmanaged table / schema drift should not break chat replies
        return
