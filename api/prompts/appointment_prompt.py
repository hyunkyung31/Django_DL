def build_appointment_prompt(
    message,
    intent_result,
    appointment=None,
    patient_context="",
):

    patient_section = ""

    if patient_context:
        patient_section = f"""
[환자 정보]

{patient_context}

==================================================
"""

    appointment_text = ""

    if appointment:

        appointment_text = f"""
[예약 정보]

예약 번호 : {appointment.get("appointment_id")}

예약일 : {appointment.get("appointment_date")}

예약 시간 : {appointment.get("appointment_time")}

진료과 : {appointment.get("department")}

담당 의사 : {appointment.get("doctor")}

예약 상태 : {appointment.get("status")}
"""

    user_prompt = f"""
{patient_section}

사용자 질문

{message}

==================================================

[의도 분석]

Intent : {intent_result["intent"]}

Confidence : {intent_result["confidence"]}

Matched Keywords : {intent_result["matched_keywords"]}

Matched Rules : {intent_result["matched_rules"]}

==================================================

{appointment_text}

==================================================

답변 규칙

1. 예약과 관련된 질문에만 답변합니다.

2. 예약 정보가 존재하면 예약 내용을 먼저 설명합니다.

3. 예약 변경을 요청하면 변경이 가능하다고 단정하지 말고,
병원 시스템을 통해 변경이 진행된다고 안내합니다.

4. 예약 취소를 요청하면 취소 가능 여부는 병원 정책에 따라 달라질 수 있다고 안내합니다.

5. 예약 조회를 요청하면
예약 날짜, 예약 시간, 담당 의사, 진료과, 예약 상태를 보기 쉽게 설명합니다.

6. 예약 정보가 없으면
예약 정보가 확인되지 않는다고 안내합니다.

7. 예약 전 준비사항을 질문하면
금식 여부, 복용 중인 약, 검사 결과, 신분증, 보험증 등 일반적인 준비사항을 안내합니다.

8. 예약 시간에 늦을 것으로 예상되면 병원으로 먼저 연락하도록 안내합니다.

9. 의료적인 진단이나 치료 판단은 하지 않습니다.

10. 답변은 5~8줄 정도로 작성합니다.

11. 항상 친절하고 이해하기 쉬운 표현을 사용합니다.
"""

    return [
        {
            "role": "user",
            "content": user_prompt
        }
    ]