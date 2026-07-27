from __future__ import annotations

from typing import Any, Literal

from schemas.annotation import BoundingBoxAnnotation


def build_detection_id(
    detection_index: int,
    *,
    frame_index: int | None = None,
) -> str:
    """
    이미지 또는 동영상 프레임의 탐지 ID를 생성한다.

    이미지:
        det_0

    동영상:
        frame_125_det_0
    """
    if detection_index < 0:
        raise ValueError("detection_index는 0 이상이어야 합니다.")

    if frame_index is None:
        return f"det_{detection_index}"

    if frame_index < 0:
        raise ValueError("frame_index는 0 이상이어야 합니다.")

    return f"frame_{frame_index}_det_{detection_index}"


def pixel_box_to_normalized(
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    image_width: int,
    image_height: int,
) -> dict[str, float]:
    """
    픽셀 xyxy 좌표를 0~1 정규화 xyxy 좌표로 변환한다.
    """
    if image_width <= 0:
        raise ValueError("image_width는 0보다 커야 합니다.")

    if image_height <= 0:
        raise ValueError("image_height는 0보다 커야 합니다.")

    if x1 < 0 or y1 < 0:
        raise ValueError("픽셀 좌표는 음수일 수 없습니다.")

    if x2 > image_width or y2 > image_height:
        raise ValueError("Bounding Box가 이미지 범위를 벗어났습니다.")

    if x1 >= x2:
        raise ValueError("x1은 x2보다 작아야 합니다.")

    if y1 >= y2:
        raise ValueError("y1은 y2보다 작아야 합니다.")

    return {
        "x1": x1 / image_width,
        "y1": y1 / image_height,
        "x2": x2 / image_width,
        "y2": y2 / image_height,
    }


def normalized_box_to_pixel(
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    image_width: int,
    image_height: int,
) -> dict[str, float]:
    """
    0~1 정규화 xyxy 좌표를 픽셀 xyxy 좌표로 변환한다.
    """
    if image_width <= 0:
        raise ValueError("image_width는 0보다 커야 합니다.")

    if image_height <= 0:
        raise ValueError("image_height는 0보다 커야 합니다.")

    coordinates = {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
    }

    for name, value in coordinates.items():
        if value < 0.0 or value > 1.0:
            raise ValueError(
                f"{name}은 0 이상 1 이하이어야 합니다."
            )

    if x1 >= x2:
        raise ValueError("x1은 x2보다 작아야 합니다.")

    if y1 >= y2:
        raise ValueError("y1은 y2보다 작아야 합니다.")

    return {
        "x1": x1 * image_width,
        "y1": y1 * image_height,
        "x2": x2 * image_width,
        "y2": y2 * image_height,
    }


def map_yolo_detection_to_annotation(
    detection: dict[str, Any],
    *,
    media_type: Literal["image", "video"] = "image",
    frame_index: int | None = None,
) -> dict[str, Any]:
    """
    기존 YOLO detection JSON을 BoundingBoxAnnotation 규격으로 변환한다.
    """
    if media_type == "video" and frame_index is None:
        raise ValueError(
            "동영상 Annotation 변환에는 frame_index가 필요합니다."
        )

    detection_index = int(detection["detection_index"])

    original_detection_id = str(
        detection.get("detection_id")
        or build_detection_id(
            detection_index,
            frame_index=frame_index,
        )
    )

    if media_type == "video":
        detection_id = build_detection_id(
            detection_index,
            frame_index=frame_index,
        )
        annotation_id = detection_id
    else:
        detection_id = original_detection_id
        annotation_id = f"image_{detection_id}"

    normalized_box = detection["box_normalized"]

    annotation = BoundingBoxAnnotation.model_validate(
        {
            "annotation_type": "bounding_box",
            "annotation_id": annotation_id,
            "detection_id": detection_id,
            "source": "ai",
            "edit_status": "original",
            "class_id": detection.get("class_id"),
            "class_name": detection.get("class_name"),
            "ai_confidence": detection.get("confidence"),
            "original_box_normalized": {
                "x1": normalized_box["x1"],
                "y1": normalized_box["y1"],
                "x2": normalized_box["x2"],
                "y2": normalized_box["y2"],
            },
            "edited_box_normalized": None,
        }
    )

    return annotation.model_dump(mode="json")


def map_yolo_detections_to_annotations(
    detections: list[dict[str, Any]],
    *,
    media_type: Literal["image", "video"] = "image",
    frame_index: int | None = None,
) -> list[dict[str, Any]]:
    """
    여러 YOLO detection을 Annotation 배열로 변환한다.
    """
    annotations = [
        map_yolo_detection_to_annotation(
            detection,
            media_type=media_type,
            frame_index=frame_index,
        )
        for detection in detections
    ]

    annotation_ids = [
        annotation["annotation_id"]
        for annotation in annotations
    ]

    if len(annotation_ids) != len(set(annotation_ids)):
        raise ValueError(
            "변환 결과에 중복된 annotation_id가 존재합니다."
        )

    return annotations