from collections import defaultdict

from api.rules.intent_keywords import INTENT_KEYWORDS
from api.rules.intent_rules import INTENT_RULES
from api.services.intent_gpt import detect_intent_gpt


def detect_intent(message: str):

    message = message.lower()

    scores = defaultdict(int)

    matched_keywords = defaultdict(list)

    matched_rules = []

    # =====================================================
    # 1. Keyword Score
    # =====================================================

    for intent, keywords in INTENT_KEYWORDS.items():

        for keyword, score in keywords.items():

            if keyword.lower() in message:

                scores[intent] += score
                matched_keywords[intent].append(keyword)

    # =====================================================
    # 2. Rule Bonus
    # =====================================================

    for rule in INTENT_RULES:

        # ---------- all ----------

        all_keywords = rule.get("all", [])

        if all_keywords:

            if not all(
                keyword.lower() in message
                for keyword in all_keywords
            ):
                continue

        # ---------- any ----------

        any_keywords = rule.get("any", [])

        if any_keywords:

            if not any(
                keyword.lower() in message
                for keyword in any_keywords
            ):
                continue

        # ---------- exclude ----------

        exclude_keywords = rule.get("exclude", [])

        if exclude_keywords:

            if any(
                keyword.lower() in message
                for keyword in exclude_keywords
            ):
                continue

        intent = rule["intent"]

        scores[intent] += rule["bonus"]

        matched_rules.append(rule["name"])

    # =====================================================
    # 3. No Intent
    # =====================================================

    if not scores:

        return {
            "intent": "general",
            "confidence": 0.0,
            "score_gap": 0,
            "scores": {},
            "matched_keywords": {},
            "matched_rules": []
        }

    # =====================================================
    # 4. Sort
    # =====================================================

    sorted_scores = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    best_intent = sorted_scores[0][0]

    best_score = sorted_scores[0][1]

    second_score = 0

    if len(sorted_scores) > 1:

        second_score = sorted_scores[1][1]

    total_score = sum(scores.values())

    confidence = round(best_score / total_score, 2)

    score_gap = best_score - second_score

    result = {

        "intent": best_intent,

        "confidence": confidence,

        "score_gap": score_gap,

        "scores": dict(sorted_scores),

        "matched_keywords": dict(matched_keywords),

        "matched_rules": matched_rules,

        "source": "rule"

    }

    # =====================================================
    # 5. GPT Backup
    # =====================================================

    if confidence < 0.6 or score_gap <= 2 or best_score < 8 :

        gpt_result = detect_intent_gpt(message)

        result["intent"] = gpt_result["intent"]

        result["confidence"] = gpt_result["confidence"]

        result["source"] = "gpt"

    return result