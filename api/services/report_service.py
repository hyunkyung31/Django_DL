from api.models import AIResult, Examination


def get_exam_result(exam_id: int):

    exam = Examination.objects.filter(
        exam_id=exam_id
    ).first()

    if exam is None:
        return None

    ai = AIResult.objects.filter(
        exam_id=exam_id
    ).first()

    if ai is None:
        return None

    return {

        # Examination
        "exam_id": exam.exam_id,
        "patient_id": exam.patient_id,
        "vessel_type": exam.vessel_type,

        # AI Result
        "has_lesion": ai.has_lesion,
        "severity_class": ai.severity_class,
        "confidence_score": ai.confidence_score,
        "heart_score": ai.heart_score,
        "mace_risk_percent": ai.mace_risk_percent,
        "doctor_opinion": ai.doctor_opinion,
        "is_confirmed": ai.is_confirmed,

        # Detection
        "bbox": ai.ai_bbox_data,
        "gradcam_path": ai.gradcam_path,
    }