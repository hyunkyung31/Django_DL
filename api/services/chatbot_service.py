from api.services.intent_service import detect_intent
from api.services.risk_service import analyze_risk
from api.services.report_service import get_exam_result
from api.services.openai_service import ask_gpt

from api.services.reference_service import get_reference_type

from api.services.context_service import build_context

from api.services.conversation_service import (
    get_session,
    create_session,
    save_user_message,
    save_assistant_message,
    get_recent_history,
)

from api.services.history_service import get_context_messages

from api.prompts.prompt_builder import build_prompt
from api.prompts.chatbot_prompt import SYSTEM_PROMPT
from api.services.risk_context_service import (
    build_risk_context,
)
from api.services.intent_context_service import (
    build_intent_context,
)

from api.services.summary_service import (
    save_summary,
)

from api.services.summary_gpt import summarize

# 첫 질문으로 세션 제목 설정 (홈 history 미리보기용)
if not session.title or session.title == "새로운 상담":
    short = (message or "").strip().replace("\n", " ")
    if short:
        session.title = short[:50]
        session.save(update_fields=["title", "updated_at"])


def chat(
    patient_id: str,
    message: str,
    session_id: int | None = None,
    exam_id: int | None = None,
):

    # ============================================
    # 0. Session 확인
    # ============================================

    session = None

    if session_id:
        session = get_session(session_id)

    if session is None:
        session = create_session(
            patient_id=patient_id
        )

    # ============================================
    # 1. Intent 분석
    # ============================================

    intent_message = build_intent_context(
        session.id,
        message,
    )

    intent_result = detect_intent(
        intent_message
    )

    # ============================================
    # 2. Risk 분석
    # ============================================

    risk_message = build_risk_context(
        session.id,
        message,
    )

    risk_result = analyze_risk(
        risk_message
    )

    # ============================================
    # 3. 검사 결과 조회
    # ============================================

    report = None

    if (
        intent_result["intent"] == "report"
        and exam_id is not None
    ):
        report = get_exam_result(exam_id)

    # ============================================
    # 4. 환자 Context 생성
    # ============================================

    patient_context = build_context(
        patient_id=patient_id,
        exam_id=exam_id,
    )

    # ============================================
    # 5. Prompt 생성
    # ============================================

    current_prompt = build_prompt(
        message=message,
        intent_result=intent_result,
        risk_result=risk_result,
        report=report,
        patient_context=patient_context,
    )

    # ============================================
    # 6. History + Prompt 결합
    # ============================================

    messages = get_context_messages(
        session_id=session.id,
        system_prompt=SYSTEM_PROMPT,
        current_prompt=current_prompt,
    )

    # ============================================
    # 7. 사용자 질문 저장
    # ============================================

    save_user_message(
        session_id=session.id,
        message=message,
        intent=intent_result["intent"],
        risk_level=risk_result["risk_level"],
        exam_id=exam_id,
        reference_type=get_reference_type(
            intent_result["intent"]
        ),
    )
    # ============================================
    # 8. GPT 호출
    # ============================================

    try:

        answer = ask_gpt(messages)

    except Exception:

        answer = (
            "죄송합니다.\n"
            "AI 응답을 생성하는 중 오류가 발생했습니다.\n"
            "잠시 후 다시 시도해주세요."
        )

    # ============================================
    # 9. GPT 답변 저장
    # ============================================

    save_assistant_message(
        session_id=session.id,
        message=answer,
        intent=intent_result["intent"],
        risk_level=risk_result["risk_level"],
        exam_id=exam_id,
        reference_type=get_reference_type(
            intent_result["intent"]
        ),
    )
    # ============================================
    # 10. Summary Memory 갱신
    # ============================================

    history = get_recent_history(
        session.id,
        limit=20,
    )

    if len(history) >= 20:

        history_text = ""

        for item in history:

            role = "사용자"

            if item.role == "assistant":
                role = "AI"

            history_text += (
                f"{role}: {item.content}\n"
            )
        try :
            summary = summarize(
                history_text
            )

            save_summary(
                session.id,
                summary,
            )
        except Exception:
            pass
        
    # ============================================
    # 11. 반환
    # ============================================

    return {

        "session_id": session.id,

        "answer": answer,

        "intent": intent_result,

        "risk": risk_result,

        "report": report,

    }