from openai import OpenAI
from django.conf import settings

client = OpenAI(
    api_key=settings.OPENAI_API_KEY
)


def ask_gpt(messages):

    response = client.chat.completions.create(

        model="gpt-5-nano",

        messages=messages,

    )

    return response.choices[0].message.content.strip()