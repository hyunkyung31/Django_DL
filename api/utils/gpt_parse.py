import json
import re


def parse_json_content(content: str, default: dict) -> dict:
    """Parse model JSON, tolerating markdown fences / surrounding text."""
    if not content:
        return default

    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if fence:
        text = fence.group(1).strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Fallback: first {...} block
    brace = re.search(r"\{.*\}", text, flags=re.S)
    if brace:
        try:
            data = json.loads(brace.group(0))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return default


def safe_intent(value, allowed, fallback="general") -> str:
    intent = str(value or "").strip().lower()
    return intent if intent in allowed else fallback


def safe_risk_level(value, fallback=0) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return fallback
    if level not in (0, 1, 2, 3):
        return fallback
    return level


def safe_confidence(value, fallback=0.0) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return fallback
    if conf < 0:
        return 0.0
    if conf > 1:
        return 1.0
    return conf
