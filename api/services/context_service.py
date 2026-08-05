from api.models import Examination
from api.models import AIResult

from api.services.patient_service import (
    build_patient_context,
)


def get_exam(exam_id):

    return Examination.objects.filter(
        exam_id=exam_id
    ).first()


def get_ai_result(exam_id):

    return AIResult.objects.filter(
        exam_id=exam_id
    ).first()


def build_context(
    patient_id,
    exam_id=None
):

    context = build_patient_context(
        patient_id
    )

    if exam_id is None:
        return context

    exam = get_exam(exam_id)

    ai = get_ai_result(exam_id)

    if exam:

        context += f"""

----------------------------------------

검사 정보

검사 번호 : {exam.exam_id}

혈관 : {exam.vessel_type}

"""

    if ai:

        context += f"""

AI 검사 결과

병변 여부 : {ai.has_lesion}

심각도 : {ai.severity_class}

AI 신뢰도 : {round(ai.confidence_score * 100, 1)} %

HEART Score : {ai.heart_score}

MACE Risk : {ai.mace_risk_percent}

의사 소견 : {ai.doctor_opinion}

"""

    return context