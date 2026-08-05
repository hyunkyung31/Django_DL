# 최근 20개만 가져오기
# 토큰 수 계산
# 오래된 대화 요약(Summary Memory)
# 중요 메시지만 추출
# 검사 결과 메시지 우선 포함

from api.services.summary_service import get_summary

from api.services.conversation_service import (
    get_recent_history,
    build_history_messages,
)


DEFAULT_HISTORY_LIMIT = 10


def get_messages(
    session_id,
    limit=DEFAULT_HISTORY_LIMIT,
):
    """
    GPT에게 전달할 최근 대화 생성
    """

    history = get_recent_history(
        session_id=session_id,
        limit=limit,
    )

    return build_history_messages(history)


def build_system_message(system_prompt):

    return {
        "role": "system",
        "content": system_prompt
    }


def build_summary_message(summary):

    return {
        "role": "system",
        "content": f"""
이전 상담 요약

{summary}
"""
    }


def get_context_messages(
    session_id,
    system_prompt,
    current_prompt,
    limit=DEFAULT_HISTORY_LIMIT,
):
    """
    OpenAI 전달용 messages 생성

    system
        ↓
    summary
        ↓
    history
        ↓
    current prompt
    """

    summary = get_summary(session_id)

    history_messages = get_messages(
        session_id=session_id,
        limit=limit,
    )

    messages = [

        build_system_message(system_prompt)

    ]

    # ===== Summary 추가 =====

    if summary:

        messages.append(
            build_summary_message(summary)
        )

    # =======================

    messages.extend(history_messages)

    messages.extend(current_prompt)

    return messages