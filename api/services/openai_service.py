from openai import OpenAI
from django.conf import settings

_client = None


def get_client() -> OpenAI:
    """Lazy OpenAI client so Django can boot without a key configured."""
    global _client
    if _client is None:
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY (or OPEN_API_KEY) is not configured in settings/.env"
            )
        _client = OpenAI(api_key=api_key)
    return _client


# Backward-compatible module attribute used by intent_gpt / risk_gpt.
class _LazyClient:
    def __getattr__(self, name):
        return getattr(get_client(), name)


client = _LazyClient()


def ask_gpt(messages):
    response = get_client().chat.completions.create(
        model="gpt-5-nano",
        messages=messages,
    )
    return response.choices[0].message.content.strip()
