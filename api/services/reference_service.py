from api.models import ChatHistory


REFERENCE_MAPPING = {

    "general": ChatHistory.ReferenceType.GENERAL,

    "symptom": ChatHistory.ReferenceType.SYMPTOM,

    "report": ChatHistory.ReferenceType.REPORT,

    "medical_term": ChatHistory.ReferenceType.MEDICAL,

    "appointment": ChatHistory.ReferenceType.APPOINTMENT,

    "lifestyle": ChatHistory.ReferenceType.LIFESTYLE,

}


def get_reference_type(intent: str):

    return REFERENCE_MAPPING.get(

        intent,

        ChatHistory.ReferenceType.GENERAL

    )


def is_report_intent(intent: str):

    return (
        get_reference_type(intent)
        == ChatHistory.ReferenceType.REPORT
    )