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

from api.services.summary_service import save_summary
from api.services.summary_gpt import summarize

import traceback


def chat(
    patient_id: str,
    message: str,
    session_id: int | None = None,
    exam_id: int | None = None,
):
    try:

        print("========== CHAT START ==========")

        # 0. Session
        print("0. Session")
        session = None

        if session_id:
            session = get_session(session_id)

        if session is None:
            session = create_session(patient_id=patient_id)

        print(f"Session OK : {session.id}")

        # 1. Intent (current message only — history context pollutes keyword scores)
        print("1. Intent")

        intent_result = detect_intent(message)

        print(intent_result)

        # 2. Risk — rules only (skip extra GPT round-trip)
        print("2. Risk")

        # Symptom-like intents can still use rule-based emergency scoring.
        # GPT risk backup is off to stay under Flutter's 60s Dio timeout.
        risk_result = analyze_risk(message, use_gpt=False)

        print(risk_result)

        # 3. Report
        print("3. Report")

        report = None

        if (
            intent_result["intent"] == "report"
            and exam_id is not None
        ):
            report = get_exam_result(exam_id)

        print("Report OK")

        # 4. Patient Context
        print("4. Context")

        patient_context = build_context(
            patient_id=patient_id,
            exam_id=exam_id,
        )

        print("Context OK")

        # 5. Prompt
        print("5. Prompt")

        current_prompt = build_prompt(
            message=message,
            intent_result=intent_result,
            risk_result=risk_result,
            report=report,
            patient_context=patient_context,
        )

        print("Prompt OK")

        # 6. History
        print("6. History")

        messages = get_context_messages(
            session_id=session.id,
            system_prompt=SYSTEM_PROMPT,
            current_prompt=current_prompt,
            limit=4,
        )

        print("History OK")

        # 7. Save User
        print("7. Save User")

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

        print("Save User OK")

        # 8. GPT
        print("8. GPT")

        try:
            answer = ask_gpt(messages)
        except Exception:
            traceback.print_exc()

            answer = (
                "죄송합니다.\n"
                "AI 응답 생성 중 오류가 발생했습니다."
            )

        print("GPT OK")

        # 9. Save Assistant
        print("9. Save Assistant")

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

        print("Save Assistant OK")

        # 10. Summary
        print("10. Summary")

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

            try:
                summary = summarize(history_text)

                save_summary(
                    session.id,
                    summary,
                )
            except Exception:
                traceback.print_exc()

        print("Summary OK")
        print("========== CHAT END ==========")

        return {
            "session_id": session.id,
            "answer": answer,
            "intent": intent_result,
            "risk": risk_result,
            "report": report,
        }

    except Exception:
        print("========== CHAT ERROR ==========")
        traceback.print_exc()
        raise