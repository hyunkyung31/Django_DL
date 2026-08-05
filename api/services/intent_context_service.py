from api.services.conversation_service import get_recent_history


def build_intent_context(
    session_id,
    current_message,
    limit=3,
):
    """
    최근 대화를 현재 질문과 합쳐
    Intent Engine이 사용할 문자열 생성
    """

    history = get_recent_history(
        session_id=session_id,
        limit=limit,
    )

    texts = []

    for item in history:

        if item.role == "user":

            texts.append(item.content)

    texts.append(current_message)

    return "\n".join(texts)