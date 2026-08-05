from api.services.openai_service import client
from api.utils.gpt_parse import parse_json_content


INTENT_LIST = [
    "symptom",
    "report",
    "medical_term",
    "appointment",
    "hospital",
    "lifestyle",
    "medicine",
    "app",
    "general",
]


def detect_intent_gpt(message: str):

    prompt = f"""
당신은 병원 AI 챗봇의 의도(Intent) 분류기입니다.

가능한 Intent는 아래 중 하나만 선택하세요.

{", ".join(INTENT_LIST)}

반드시 아래 JSON 형식으로만 답변하세요.

{{
    "intent": "...",
    "confidence": 0.95
}}

사용자 입력:
{message}
"""

    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {
                "role": "system",
                "content": "당신은 Intent Classifier입니다. JSON만 반환하세요.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        timeout=20,
    )

    content = (response.choices[0].message.content or "").strip()
    return parse_json_content(
        content,
        default={"intent": "general", "confidence": 0.0},
    )