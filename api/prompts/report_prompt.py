def build_report_prompt(
    message,
    intent_result,
    risk_result,
    report,
    patient_context="",
):

    patient_section = ""

    if patient_context:
        patient_section = f"""
[환자 정보]

{patient_context}

==================================================
"""

    report_text = ""

    if report:

        report_text = f"""
[AI 검사 결과]

검사 번호 : {report["exam_id"]}

혈관 : {report["vessel_type"]}

병변 여부 : {report["has_lesion"]}

심각도 : {report["severity_class"]}

AI 신뢰도 : {report["confidence_score"]}

HEART Score : {report["heart_score"]}

MACE Risk : {report["mace_risk_percent"]}

의사 소견 : {report["doctor_opinion"]}

Bounding Box : {report["bbox"]}
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

[위험도 분석]

Risk Level : {risk_result["risk_level"]}

Risk Score : {risk_result["score"]}

Risk Message : {risk_result["message"]}

Risk Source : {risk_result["source"]}

Matched Keywords : {risk_result["matched_keywords"]}

Matched Rules : {risk_result["matched_rules"]}

Category Scores : {risk_result["category_scores"]}

==================================================

{report_text}

==================================================

답변 규칙

1. AI 검사 결과를 일반인이 이해하기 쉬운 표현으로 설명합니다.

2. 전문 의학용어는 반드시 쉬운 말로 설명합니다.

예시
- Stenosis → 혈관이 좁아진 상태
- Plaque → 혈관 안에 쌓인 지방 찌꺼기
- Calcification → 혈관이 딱딱하게 굳은 상태
- LAD → 심장 앞쪽 관상동맥
- RCA → 오른쪽 관상동맥
- LCX → 왼쪽 회선 관상동맥

3. AI 결과는 참고 자료이며 확정 진단이라고 표현하지 않습니다.

4. HEART Score와 MACE Risk가 있다면
각 점수가 무엇을 의미하는지 환자가 이해하기 쉽게 설명합니다.

5. 병변이 발견된 경우에는
생활습관 개선, 금연, 혈압·당뇨·콜레스테롤 관리의 중요성을 함께 안내합니다.

6. Risk Level과 AI 검사 결과를 함께 고려하여 답변합니다.
응급 위험이 높으면 즉시 119 또는 응급실 방문을 권고합니다.

7. 의사 소견이 존재하면 가장 우선하여 설명합니다.

8. 환자가 불안감을 느끼지 않도록 차분하고 친절한 말투를 사용합니다.

9. 답변은 6~10줄 정도로 작성합니다.

10. 마지막에는 반드시
"최종 진단과 치료 계획은 담당 의료진과 상담하시기 바랍니다."
라는 취지의 안내를 포함합니다.
"""

    return [
        {
            "role": "user",
            "content": user_prompt
        }
    ]