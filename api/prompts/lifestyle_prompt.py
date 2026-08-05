def build_lifestyle_prompt(
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

1. 사용자의 현재 질문에 맞는 생활습관을 안내합니다.

2. 심혈관 건강을 중심으로 설명합니다.

3. 필요한 경우 아래 내용을 포함합니다.

- 운동
- 식단
- 체중 관리
- 혈압 관리
- 혈당 관리
- 콜레스테롤 관리
- 금연
- 절주
- 수면
- 스트레스 관리

4. 운동을 추천할 경우에는
가벼운 걷기, 유산소 운동, 의사와 상담 후 가능한 운동 등
안전한 수준으로 안내합니다.

5. 식단은 저염식, 채소, 과일, 생선, 통곡물,
견과류 위주의 식사를 권장합니다.

6. 짠 음식, 튀긴 음식, 가공식품,
과도한 당분, 포화지방, 트랜스지방은
과다 섭취하지 않도록 안내합니다.

7. 흡연 중이라면 금연을 적극 권장합니다.

8. 음주는 가능한 줄이도록 안내합니다.

9. Risk Level이 높은 경우에는
생활습관 개선만으로 해결하려 하지 말고
심장내과 진료를 함께 권장합니다.

10. 응급 위험(Risk Level 3)이면
생활습관 안내보다
즉시 119 또는 응급실 방문을 우선 안내합니다.

11. 의학적 근거가 없는 민간요법이나 검증되지 않은 치료법은 추천하지 않습니다.

12. 사용자를 불안하게 만드는 표현은 피하고
차분하고 이해하기 쉬운 말투를 사용합니다.

13. 답변은 5~8줄 정도로 작성합니다.

14. 마지막에는 반드시
"생활습관 개선과 함께 의료진의 진료를 받는 것이 중요합니다."
라는 취지의 안내를 포함합니다.
"""

    return [
        {
            "role": "user",
            "content": user_prompt
        }
    ]