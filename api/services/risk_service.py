from collections import defaultdict

from api.rules.keywords import (
    LOW_RISK,
    MEDIUM_RISK,
    HIGH_RISK,
    HIGH_RISK_KEYWORDS,
)

from api.rules.emergency import EMERGENCY_RULES
from api.rules.time_keywords import TIME_KEYWORDS
from api.rules.onset_keywords import ONSET_KEYWORDS
from api.rules.severity_keywords import SEVERITY_KEYWORDS
from api.rules.risk_factor import RISK_FACTORS
from api.rules.risk_level import RISK_LEVEL
from api.rules.risk_weights import RISK_WEIGHTS

from api.services.risk_gpt import detect_risk_gpt
from api.utils.gpt_parse import safe_risk_level, safe_confidence


def analyze_risk(message: str):

    message_lower = message.lower()

    score = 0

    matched_keywords = set()
    matched_rules = set()

    category_scores = defaultdict(int)

    score_detail = []

    # ============================================
    # HIGH_RISK_KEYWORDS
    # ============================================

    for keyword, value in HIGH_RISK_KEYWORDS.items():

        if keyword.lower() in message_lower:

            score += value

            category_scores["keyword"] += value

            matched_keywords.add(keyword)

            score_detail.append({
                "type": "keyword",
                "name": keyword,
                "score": value
            })

    # ============================================
    # LOW
    # ============================================

    for keyword, value in LOW_RISK.items():

        if keyword.lower() in message_lower:

            score += value

            category_scores["low"] += value

            matched_keywords.add(keyword)

            score_detail.append({
                "type": "low",
                "name": keyword,
                "score": value
            })

    # ============================================
    # MEDIUM
    # ============================================

    for keyword, value in MEDIUM_RISK.items():

        if keyword.lower() in message_lower:

            score += value

            category_scores["medium"] += value

            matched_keywords.add(keyword)

            score_detail.append({
                "type": "medium",
                "name": keyword,
                "score": value
            })

    # ============================================
    # HIGH
    # ============================================

    for keyword, value in HIGH_RISK.items():

        if keyword.lower() in message_lower:

            score += value

            category_scores["high"] += value

            matched_keywords.add(keyword)

            score_detail.append({
                "type": "high",
                "name": keyword,
                "score": value
            })

    # ============================================
    # Emergency Rule
    # ============================================

    for rule in EMERGENCY_RULES:

        all_keywords = rule.get("all", [])

        if all_keywords:
            if not all(k.lower() in message_lower for k in all_keywords):
                continue

        any_keywords = rule.get("any", [])

        if any_keywords:
            if not any(k.lower() in message_lower for k in any_keywords):
                continue

        bonus = rule["risk"] * RISK_WEIGHTS["emergency"]

        score += bonus

        category_scores["emergency"] += bonus

        matched_rules.add(rule["name"])

        score_detail.append({
            "type": "emergency",
            "name": rule["name"],
            "score": bonus
        })

    # ============================================
    # Time
    # ============================================

    time_score = 0

    for keywords in TIME_KEYWORDS.values():

        for keyword in keywords:

            if keyword.lower() in message_lower:

                time_score = max(
                    time_score,
                    RISK_WEIGHTS["time"]
                )

                matched_rules.add(keyword)

    score += time_score
    category_scores["time"] = time_score

    if time_score:
        score_detail.append({
            "type": "time",
            "score": time_score
        })

    # ============================================
    # Onset
    # ============================================

    onset_score = 0

    for keywords in ONSET_KEYWORDS.values():

        for keyword in keywords:

            if keyword.lower() in message_lower:

                onset_score = max(
                    onset_score,
                    RISK_WEIGHTS["onset"]
                )

                matched_rules.add(keyword)

    score += onset_score
    category_scores["onset"] = onset_score

    if onset_score:
        score_detail.append({
            "type": "onset",
            "score": onset_score
        })

    # ============================================
    # Severity
    # ============================================

    severity_score = 0

    for keywords in SEVERITY_KEYWORDS.values():

        for keyword in keywords:

            if keyword.lower() in message_lower:

                severity_score = max(
                    severity_score,
                    RISK_WEIGHTS["severity"]
                )

                matched_rules.add(keyword)

    score += severity_score
    category_scores["severity"] = severity_score

    if severity_score:
        score_detail.append({
            "type": "severity",
            "score": severity_score
        })
# 6. Risk Factor

    for keyword, value in RISK_FACTORS.items():

        if keyword.lower() in message:

            bonus = value * RISK_WEIGHTS["risk_factor"]
            score += bonus
            category_scores["risk_factor"] += bonus

            matched_rules.add(keyword)

    # ============================================
    # Risk Factor
    # ============================================

    for keyword, value in RISK_FACTORS.items():

        if keyword.lower() in message_lower:

            bonus = value * RISK_WEIGHTS["risk_factor"]

            score += bonus

            category_scores["risk_factor"] += bonus

            matched_rules.add(keyword)

            score_detail.append({
                "type": "risk_factor",
                "name": keyword,
                "score": bonus
            })

    # ============================================
    # Risk Level
    # ============================================

    risk_level = 0
    risk_message = ""

    for level, info in RISK_LEVEL.items():

        if info["min"] <= score <= info["max"]:

            risk_level = level
            risk_message = info["message"]
            break

    # ============================================
    # Confidence
    # ============================================

    confidence = min(round(score / 100, 2), 1.0)

    # ============================================
    # GPT Backup
    # ============================================

    source = "rule"

    if confidence < 0.6 or score < 20:
        try:
            gpt_result = detect_risk_gpt(message)

            risk_level = safe_risk_level(
                gpt_result.get("risk_level"),
                fallback=risk_level,
            )
            confidence = safe_confidence(
                gpt_result.get("confidence"),
                fallback=confidence,
            )
            risk_message = gpt_result.get("reason", risk_message) or risk_message
            source = "gpt"
        except Exception:
            source = "rule_gpt_failed"

    # ============================================
    # Return
    # ============================================

    return {

        "risk_level": int(risk_level),

        "score": score,

        "confidence": confidence,

        "message": risk_message,

        "matched_keywords": sorted(matched_keywords),

        "matched_rules": sorted(matched_rules),

        "category_scores": dict(category_scores),

        "score_detail": score_detail,

        "source": source

    }