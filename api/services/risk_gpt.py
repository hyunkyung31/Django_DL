from api.services.openai_service import client
from api.utils.gpt_parse import (
    parse_json_content,
    safe_confidence,
    safe_risk_level,
)


def detect_risk_gpt(message: str):

    prompt = f"""
당신은 심혈관 질환 위험도를 평가하는 의료 AI입니다.

사용자의 증상을 보고 아래 기준 중 하나를 선택하세요.

0 : 정상
1 : 주의
2 : 빠른 병원 방문 권장
3 : 즉시 119 또는 응급실

반드시 JSON만 출력하세요.

예시

{{
    "risk_level": 2,
    "confidence": 0.93,
    "reason": "..."
}}

사용자 입력

{message}
"""

    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {
                "role": "system",
                "content": "당신은 심혈관 응급도 분류 AI입니다. JSON만 반환하세요.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        timeout=20,
    )

    content = (response.choices[0].message.content or "").strip()
    parsed = parse_json_content(
        content,
        default={
            "risk_level": 0,
            "confidence": 0.0,
            "reason": "GPT Parsing Error",
        },
    )
    return {
        "risk_level": safe_risk_level(parsed.get("risk_level"), fallback=0),
        "confidence": safe_confidence(parsed.get("confidence"), fallback=0.0),
        "reason": str(parsed.get("reason") or ""),
    }