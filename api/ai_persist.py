"""
exam keyframe → AI 서버 추론 → bbox(JSON) + heatmap(GCS/local) 영구 저장.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Optional

import requests
from django.conf import settings

from api.media_utils import download_media_bytes, save_media_bytes
from api.models import AIResult, Examination

logger = logging.getLogger(__name__)


class AiPersistError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _call_analysis_image(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
) -> dict[str, Any]:
    url = f"{settings.AI_SERVER_URL.rstrip('/')}/analysis/image"
    files = {
        "file": (filename, image_bytes, content_type or "application/octet-stream"),
    }
    params = {
        "confidence_threshold": confidence_threshold,
        "iou_threshold": iou_threshold,
    }

    try:
        response = requests.post(url, files=files, params=params, timeout=180)
    except requests.RequestException as exc:
        raise AiPersistError(f"AI 서버 연결 실패: {exc}", status_code=502) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise AiPersistError(
            f"AI 서버 응답 파싱 실패: {response.text[:300]}",
            status_code=502,
        ) from exc

    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        raise AiPersistError(
            f"AI 서버 추론 실패({response.status_code}): {detail}",
            status_code=502,
        )

    if not isinstance(payload, dict):
        raise AiPersistError("AI 서버 응답 형식이 올바르지 않습니다.", status_code=502)

    return payload


def _decode_overlay_png(classification: dict[str, Any]) -> Optional[bytes]:
    """prefer overlay → transparent heatmap → colored heatmap."""
    for key in ("overlay_base64", "heatmap_base64"):
        raw = classification.get(key)
        if not raw:
            continue
        try:
            return base64.b64decode(raw)
        except Exception:
            logger.warning("base64 디코딩 실패: %s", key)
    return None


def _build_bbox_payload(detection: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": "best_yolo.pt",
        "image_width": detection.get("image_width"),
        "image_height": detection.get("image_height"),
        "detection_count": int(detection.get("detection_count") or 0),
        "detections": detection.get("detections") or [],
    }


def _map_severity(
    predicted_label: str,
    detection_count: int,
) -> tuple[bool, str]:
    label = (predicted_label or "unknown").strip()
    lowered = label.lower()
    has_lesion = lowered == "stenosis" or detection_count > 0
    if not label:
        label = "Stenosis" if has_lesion else "Normal"
    return has_lesion, label


def run_and_persist_exam_ai(
    exam_id: int,
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
) -> dict[str, Any]:
    """
    examinations.key_frame_path 이미지를 읽어 AI 추론 후 ai_results에 저장.
    heatmap은 GCS(설정 시) 또는 MEDIA_ROOT에 저장하고 gradcam_path에 경로만 기록.
    """
    exam = Examination.objects.filter(exam_id=exam_id).first()
    if exam is None:
        raise AiPersistError("검사를 찾을 수 없습니다.", status_code=404)

    if not exam.key_frame_path:
        raise AiPersistError(
            "key_frame_path가 비어 있습니다. 원본 키프레임을 먼저 업로드하세요.",
            status_code=400,
        )

    try:
        image_bytes, filename, content_type = download_media_bytes(exam.key_frame_path)
    except FileNotFoundError as exc:
        raise AiPersistError(str(exc), status_code=404) from exc

    payload = _call_analysis_image(
        image_bytes=image_bytes,
        filename=filename,
        content_type=content_type,
        confidence_threshold=confidence_threshold,
        iou_threshold=iou_threshold,
    )

    classification = payload.get("classification") or {}
    detection = payload.get("detection") or {}
    if not isinstance(classification, dict):
        classification = {}
    if not isinstance(detection, dict):
        detection = {}

    ai_bbox_data = _build_bbox_payload(detection)
    predicted_label = str(classification.get("predicted_label") or "unknown")
    confidence = float(classification.get("confidence") or 0.0)
    has_lesion, severity_class = _map_severity(
        predicted_label,
        ai_bbox_data["detection_count"],
    )

    gradcam_path = None
    overlay_png = _decode_overlay_png(classification)
    if overlay_png:
        gradcam_path = save_media_bytes(
            patient_id=exam.patient_id,
            media_type="gradcam",
            filename=f"{exam.exam_id}_gradcam_overlay.png",
            content=overlay_png,
            content_type="image/png",
        )

    ai = AIResult.objects.filter(exam_id=exam.exam_id).first()
    if ai is None:
        ai = AIResult(exam_id=exam.exam_id)

    ai.has_lesion = has_lesion
    ai.severity_class = severity_class
    ai.confidence_score = confidence
    ai.ai_bbox_data = ai_bbox_data
    if gradcam_path:
        ai.gradcam_path = gradcam_path
    ai.is_confirmed = False
    ai.save()

    return {
        "exam_id": exam.exam_id,
        "patient_id": exam.patient_id,
        "key_frame_path": exam.key_frame_path,
        "has_lesion": ai.has_lesion,
        "severity_class": ai.severity_class,
        "confidence_score": ai.confidence_score,
        "ai_bbox_data": ai.ai_bbox_data,
        "gradcam_path": ai.gradcam_path,
        "show_gradcam": bool(classification.get("show_gradcam")),
        "probabilities": classification.get("probabilities"),
        "analysis_id": payload.get("analysis_id"),
    }