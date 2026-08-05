def build_symptom_prompt(
    message,
    intent_result,
    risk_result,
    patient_context="",
):

    patient_section = ""

    if patient_context:
        patient_section = f"""
[환자 정보]

{patient_context}

==================================================
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

답변 규칙

1. 먼저 사용자의 증상에 공감하며 답변을 시작합니다.

2. 현재 증상이 어떤 심혈관 질환에서 나타날 수 있는지
가능성만 설명합니다.
절대로 확정 진단하지 않습니다.

3. 응급 위험도(Risk Level 3 또는 응급 증상)가 높으면
즉시 119 또는 응급실 방문을 가장 먼저 권고합니다.

4. 위험도가 중간(Risk Level 2)이면
빠른 심장내과 방문을 권고합니다.

5. 위험도가 낮으면
생활습관 개선과 경과 관찰을 안내합니다.

6. 생활습관은 환자의 상태에 맞게 설명합니다.
예를 들어 운동, 식단, 금연, 혈압, 당뇨,
콜레스테롤, 체중 관리 등을 포함할 수 있습니다.

7. 의학용어는 일반인이 이해하기 쉬운 표현으로 설명합니다.

8. 답변은 자연스럽고 친절하게 작성하며
불필요한 반복은 하지 않습니다.

9. 답변은 5~8줄 정도로 작성합니다.

10. 마지막에는 반드시
"정확한 진단은 의료진의 진료가 필요합니다."
라는 취지의 안내를 포함합니다.
"""

    return [
        {
            "role": "user",
            "content": user_prompt
        }
    ]