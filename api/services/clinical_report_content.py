from __future__ import annotations

from typing import Any


def safe_text(
    value: Any,
    default: str = "-",
) -> str:
    if value is None:
        return default

    text = str(value).strip()
    return text or default


def _resolve_analysis_state(
    ai_result: dict[str, Any],
) -> str:
    """
    기존 데이터 구조에서 환자 보고서용 분석 상태를 결정한다.

    현재 severity_class 필드는 이름과 달리
    Normal/Stenosis 분류 결과를 저장하는 용도로 사용한다.
    중증도 분류 기능은 없으므로 경도/중등도/중증으로 해석하지 않는다.
    """
    has_lesion = ai_result.get("has_lesion")

    classification = safe_text(
        ai_result.get("severity_class"),
        default="",
    ).lower()

    if has_lesion is True or classification == "stenosis":
        return "stenosis"

    if classification in {"normal", "none"}:
        return "normal"

    if has_lesion is False and not classification:
        return "normal"

    return "review_required"


def build_patient_ai_result_label(
    ai_result: dict[str, Any] | None,
) -> str:
    """
    환자 보고서 표에 표시할 짧은 AI 보조 분석 결과를 생성한다.
    """
    result = ai_result or {}
    state = _resolve_analysis_state(result)

    if state == "stenosis":
        return "협착이 의심되는 부위가 탐지되었습니다."

    if state == "normal":
        return "뚜렷한 협착 의심 부위가 탐지되지 않았습니다."

    return "AI 분석 결과에 대한 의료진 확인이 필요합니다."


def build_patient_ai_summary(
    ai_result: dict[str, Any] | None,
) -> str:
    """
    환자가 이해할 수 있는 AI 보조 분석 요약을 생성한다.

    숫자형 모델 신뢰도는 환자에게 질환 확률이나 진단 정확도로
    오해될 수 있으므로 포함하지 않는다.
    """
    result = ai_result or {}
    state = _resolve_analysis_state(result)

    if state == "stenosis":
        return (
            "AI가 관상동맥 조영 영상을 분석한 결과, "
            "협착이 의심되는 부위가 탐지되었습니다. "
            "이 결과는 의료진의 판독을 보조하기 위한 정보이며, "
            "질환을 확정하는 최종 진단 결과가 아닙니다."
        )

    if state == "normal":
        return (
            "AI가 관상동맥 조영 영상을 분석한 결과, "
            "뚜렷한 협착 의심 부위는 탐지되지 않았습니다. "
            "다만 AI 분석만으로 정상 여부를 확정할 수 없으며, "
            "담당 의료진의 종합적인 판독 결과를 함께 확인해야 합니다."
        )

    return (
        "현재 저장된 AI 분석 정보만으로는 결과를 명확하게 "
        "설명하기 어렵습니다. 아래 의료진 최종 소견을 확인해 주세요."
    )


def build_patient_xai_explanation(
    ai_result: dict[str, Any] | None,
) -> str:
    """
    환자 보고서의 'AI 분석에 대한 안내' 문장을 생성한다.

    환자에게는 '설명 가능한 AI' 또는 'XAI' 같은 기술 용어를
    직접 노출하지 않고, AI 분석의 역할과 한계를 설명한다.
    """
    result = ai_result or {}
    state = _resolve_analysis_state(result)

    if state == "stenosis":
        return (
            "이 결과는 관상동맥 조영 영상을 AI가 분석하여 생성한 "
            "의료진 판독 보조 정보입니다. AI 분석에서 협착이 의심되는 "
            "부위가 탐지되었으며, 담당 의료진은 원본 영상과 환자의 "
            "임상 정보를 함께 검토하여 최종 소견을 작성했습니다. "
            "AI 분석 결과만으로 질환을 확정하거나 치료 방법을 "
            "결정할 수 없습니다."
        )

    if state == "normal":
        return (
            "이 결과는 관상동맥 조영 영상을 AI가 분석하여 생성한 "
            "의료진 판독 보조 정보입니다. AI 분석에서는 뚜렷한 협착 "
            "의심 부위가 탐지되지 않았습니다. 다만 이 결과만으로 "
            "질환이 없음을 확정할 수 없으며, 담당 의료진이 원본 영상과 "
            "환자의 임상 정보를 함께 검토하여 최종 소견을 작성했습니다."
        )

    return (
        "현재 저장된 AI 분석 정보만으로는 AI 분석 내용을 명확하게 "
        "설명하기 어렵습니다. 최종 결과는 아래 의료진 소견을 "
        "확인해 주세요."
    )


def clean_final_result(value: Any) -> str:
    """
    의료진 최종 소견에 포함된 내부 관리용 접두어를 제거한다.
    의료진이 작성하거나 최종 승인한 본문은 변경하지 않는다.
    """
    text = safe_text(value)

    removable_prefixes = (
        "[AI 자동 생성 소견]",
        "[의료진 최종 소견]",
    )

    for prefix in removable_prefixes:
        if text.startswith(prefix):
            cleaned = text[len(prefix):].strip()
            return cleaned or "-"

    return text