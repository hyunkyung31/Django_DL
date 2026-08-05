from collections import defaultdict

from api.rules.intent_keywords import INTENT_KEYWORDS
from api.rules.intent_rules import INTENT_RULES
from api.utils.keyword_match import keyword_in_text


ALLOWED_INTENTS = {
    "symptom",
    "report",
    "medical_term",
    "appointment",
    "hospital",
    "lifestyle",
    "medicine",
    "app",
    "general",
}


def detect_intent(message: str):
    """Rule-only intent detection for low latency.

    OpenAI intent backup was removed from the hot path because Flutter Dio
    receiveTimeout is 60s and multiple GPT round-trips commonly exceed it.
    """

    message = (message or "").lower()
    scores = defaultdict(int)
    matched_keywords = defaultdict(list)
    matched_rules = []

    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword, score in keywords.items():
            if keyword_in_text(keyword, message):
                scores[intent] += score
                matched_keywords[intent].append(keyword)

    for rule in INTENT_RULES:
        all_keywords = rule.get("all", [])
        if all_keywords and not all(
            keyword_in_text(keyword, message) for keyword in all_keywords
        ):
            continue

        any_keywords = rule.get("any", [])
        if any_keywords and not any(
            keyword_in_text(keyword, message) for keyword in any_keywords
        ):
            continue

        exclude_keywords = rule.get("exclude", [])
        if exclude_keywords and any(
            keyword_in_text(keyword, message) for keyword in exclude_keywords
        ):
            continue

        scores[rule["intent"]] += rule["bonus"]
        matched_rules.append(rule["name"])

    if not scores:
        return {
            "intent": "general",
            "confidence": 0.0,
            "score_gap": 0,
            "scores": {},
            "matched_keywords": {},
            "matched_rules": [],
            "source": "rule",
        }

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_intent = sorted_scores[0][0]
    best_score = sorted_scores[0][1]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0
    total_score = sum(scores.values())

    return {
        "intent": best_intent if best_intent in ALLOWED_INTENTS else "general",
        "confidence": round(best_score / total_score, 2),
        "score_gap": best_score - second_score,
        "scores": dict(sorted_scores),
        "matched_keywords": dict(matched_keywords),
        "matched_rules": matched_rules,
        "source": "rule",
    }
