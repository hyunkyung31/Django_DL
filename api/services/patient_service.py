from api.models import Patient


def get_patient(patient_id):

    return Patient.objects.filter(
        patient_id=patient_id
    ).first()


def get_patient_summary(patient_id):

    patient = get_patient(patient_id)

    if patient is None:
        return None

    return {

        "patient_id": patient.patient_id,

        "name": patient.patient_name,

        "gender": patient.gender,

        "age": patient.age,

        "history_score": patient.history_score,

        "ecg_result": patient.ecg_result,

        "risk_factors_count": patient.risk_factors_count,

        "troponin_t_level": patient.troponin_t_level,

        "underlying_diseases": patient.underlying_diseases,

        "chief_complaint": patient.chief_complaint,

    }


def build_patient_context(patient_id):

    patient = get_patient_summary(patient_id)

    if patient is None:
        return ""

    return f"""
환자 정보

이름 : {patient["name"]}

성별 : {patient["gender"]}

나이 : {patient["age"]}

기저질환 : {patient["underlying_diseases"]}

주호소 : {patient["chief_complaint"]}

ECG 결과 : {patient["ecg_result"]}

Troponin-T : {patient["troponin_t_level"]}

History Score : {patient["history_score"]}

위험인자 개수 : {patient["risk_factors_count"]}
"""