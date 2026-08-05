from api.models import ConversationMemory


def get_summary(session_id):
    """
    저장된 Summary 반환
    """

    memory = ConversationMemory.objects.filter(
        session_id=session_id,
    ).first()

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

    memory = ConversationMemory.objects.filter(
        session_id=session_id,
    ).first()

    if memory is None:

        memory = ConversationMemory(
            session_id=session_id,
        )

    memory.summary = summary

    memory.save()