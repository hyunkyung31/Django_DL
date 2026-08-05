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
        # Keep per-request timeouts modest so gunicorn workers are less likely
        # to hit the default 30s hard kill and return HTML 500 to Flutter.
        _client = OpenAI(api_key=api_key, timeout=25.0, max_retries=1)
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
        timeout=25,
    )
    content = response.choices[0].message.content
    return (content or "").strip()
