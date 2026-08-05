from api.services.openai_service import ask_gpt


def summarize(history_messages):

    prompt = f"""
아래 대화를 의료 기록처럼 요약하세요.

조건

- 환자의 주요 증상
- 위험요인
- 검사결과
- 의사의 조언

5줄 이하

대화

{history_messages}
"""

    messages = [

        {
            "role":"system",
            "content":"당신은 의료 상담 내용을 요약하는 AI입니다."
        },

        {
            "role":"user",
            "content":prompt
        }

    ]

    return ask_gpt(messages)