from api.prompts.symptom_prompt import build_symptom_prompt
from api.prompts.report_prompt import build_report_prompt
from api.prompts.medical_prompt import build_medical_prompt
from api.prompts.appointment_prompt import build_appointment_prompt
from api.prompts.lifestyle_prompt import build_lifestyle_prompt


def build_prompt(
    message,
    intent_result,
    risk_result,
    report=None,
    patient_context="",
):

    intent = intent_result["intent"]

    if intent == "report":
        return build_report_prompt(
            message=message,
            intent_result=intent_result,
            risk_result=risk_result,
            report=report,
            patient_context=patient_context,
        )

    elif intent == "medical_term":
        return build_medical_prompt(
            message=message,
            intent_result=intent_result,
            risk_result=risk_result,
            patient_context=patient_context,
        )

    elif intent == "appointment":
        return build_appointment_prompt(
            message=message,
            intent_result=intent_result,
            patient_context=patient_context,
        )

    elif intent == "lifestyle":
        return build_lifestyle_prompt(
            message=message,
            intent_result=intent_result,
            risk_result=risk_result,
            patient_context=patient_context,
        )

    else:
        return build_symptom_prompt(
            message=message,
            intent_result=intent_result,
            risk_result=risk_result,
            patient_context=patient_context,
        )