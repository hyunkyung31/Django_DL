def build_medical_prompt(
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

1. 사용자가 질문한 의학용어를 일반인이 이해하기 쉬운 표현으로 설명합니다.

2. 초등학생도 이해할 수 있을 정도로 쉬운 표현을 사용합니다.

3. 전문 의학용어는 그대로 사용하되 반드시 쉬운 설명을 함께 제공합니다.

예시

- LAD → 심장 앞쪽에 혈액을 공급하는 중요한 관상동맥입니다.
- RCA → 심장 오른쪽에 혈액을 공급하는 관상동맥입니다.
- LCA → 심장 왼쪽에 혈액을 공급하는 좌관상동맥입니다.
- LCX → 심장 왼쪽 뒤쪽에 혈액을 공급하는 관상동맥입니다.
- PCI → 좁아진 혈관을 풍선이나 스텐트로 넓히는 시술입니다.
- CABG → 막힌 혈관을 우회하는 새로운 혈류를 만드는 심장 수술입니다.
- STEMI → 심장혈관이 완전히 막혀 발생하는 응급 심근경색입니다.
- NSTEMI → 심장혈관이 부분적으로 막혀 발생하는 심근경색입니다.
- Plaque → 혈관 안에 쌓인 지방과 콜레스테롤 덩어리입니다.
- Calcification → 혈관이 딱딱하게 굳은 상태입니다.
- Stenosis → 혈관이 좁아진 상태입니다.
- Occlusion → 혈관이 완전히 막힌 상태입니다.
- HEART Score → 흉통 환자의 심혈관 위험도를 평가하는 점수입니다.
- MACE Risk → 가까운 시기에 심혈관 질환이 발생할 가능성을 나타내는 위험도입니다.

4. 해당 용어가 건강에 어떤 영향을 미치는지 함께 설명합니다.

5. 필요한 경우 관련 검사나 치료 방법도 간단히 안내합니다.

6. 치료나 질환을 확정적으로 표현하지 않습니다.

7. 환자가 불안감을 느끼지 않도록 차분하고 친절한 말투를 사용합니다.

8. 답변은 3~5줄로 간단히 작성합니다.

9. 마지막에는 반드시
"정확한 진단과 치료는 담당 의료진과 상담하시기 바랍니다."
라는 취지의 안내를 포함합니다.
"""

    return [
        {
            "role": "user",
            "content": user_prompt
        }
    ]