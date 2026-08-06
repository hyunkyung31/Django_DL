from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent.parent
# VM에는 seg best 가중치를 이 경로로 올린다 (파일명은 유지).
# 모델 task는 segment여도 제품 API는 bbox detection만 반환한다.
MODEL_PATH = BASE_DIR / "models" / "best_yolo.pt"

# stenosis seg best 실험 기본값 (제품은 bbox만 사용)
YOLO_IMAGE_SIZE = 640
YOLO_CONFIDENCE_THRESHOLD = 0.35
YOLO_IOU_THRESHOLD = 0.45

# detect 전용 가중치와 seg 가중치(bbox만 사용) 모두 허용
ALLOWED_YOLO_TASKS = frozenset({"detect", "segment"})


def load_yolo_model() -> YOLO:
    """
    YOLO 모델을 로딩한다.

    detect 가중치와 segment 가중치를 모두 허용한다.
    segment여도 추론 응답에서는 Bounding Box만 사용한다.

    Raises:
        FileNotFoundError:
            가중치 파일이 존재하지 않을 때 발생한다.
        ValueError:
            로딩된 가중치가 허용되지 않은 task일 때 발생한다.
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"YOLO 가중치 파일을 찾을 수 없습니다: {MODEL_PATH}"
        )

    loaded_model = YOLO(str(MODEL_PATH))
    task = str(loaded_model.task)

    if task not in ALLOWED_YOLO_TASKS:
        raise ValueError(
            "현재 가중치는 지원하지 않는 YOLO task입니다. "
            f"허용: {sorted(ALLOWED_YOLO_TASKS)}, 확인된 task: {task}"
        )

    return loaded_model


# 가중치가 없어도 서버는 기동하고, 실제 탐지 시점에 로딩한다.
yolo_model: YOLO | None = None


def get_yolo_model() -> YOLO:
    """필요할 때 YOLO 모델을 한 번만 로딩한다."""
    global yolo_model
    if yolo_model is None:
        yolo_model = load_yolo_model()
    return yolo_model


def get_model_information() -> dict[str, Any]:
    """
    현재 로딩된 YOLO 모델의 기본 정보를 반환한다.
    가중치가 없으면 loaded=False 형태의 요약만 반환한다.
    """
    if not MODEL_PATH.exists():
        return {
            "model_name": MODEL_PATH.name,
            "loaded": False,
            "task": None,
            "product_mode": "detection",
            "class_count": 0,
            "class_names": {},
            "image_size": YOLO_IMAGE_SIZE,
            "confidence_threshold": YOLO_CONFIDENCE_THRESHOLD,
            "iou_threshold": YOLO_IOU_THRESHOLD,
            "detail": f"weights missing: {MODEL_PATH}",
        }

    model = get_yolo_model()
    class_names = {
        int(class_id): str(class_name)
        for class_id, class_name in model.names.items()
    }

    return {
        "model_name": MODEL_PATH.name,
        "loaded": True,
        "task": str(model.task),
        # seg 가중치여도 API/프론트 계약은 bbox detection
        "product_mode": "detection",
        "class_count": len(class_names),
        "class_names": class_names,
        "image_size": YOLO_IMAGE_SIZE,
        "confidence_threshold": YOLO_CONFIDENCE_THRESHOLD,
        "iou_threshold": YOLO_IOU_THRESHOLD,
    }


def detect_image(
    image: Image.Image | np.ndarray,
    confidence_threshold: float = YOLO_CONFIDENCE_THRESHOLD,
    iou_threshold: float = YOLO_IOU_THRESHOLD,
) -> dict[str, Any]:
    """
    PIL 이미지 또는 NumPy 배열 한 장을 입력받아 객체 탐지를 수행한다.

    segment 모델이어도 masks는 무시하고 boxes만 반환한다.

    Args:
        image:
            PIL.Image.Image 또는 OpenCV/NumPy 이미지 배열.
        confidence_threshold:
            반환할 탐지 결과의 최소 confidence.
        iou_threshold:
            NMS 과정에서 사용할 IoU threshold.

    Returns:
        이미지 크기, 탐지 개수, Bounding Box 목록을 포함한 딕셔너리.
    """
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError(
            "confidence_threshold는 0 이상 1 이하이어야 합니다."
        )

    if not 0.0 <= iou_threshold <= 1.0:
        raise ValueError(
            "iou_threshold는 0 이상 1 이하이어야 합니다."
        )

    if isinstance(image, Image.Image):
        input_image = image.convert("RGB")
        image_width, image_height = input_image.size
    elif isinstance(image, np.ndarray):
        if image.ndim not in (2, 3):
            raise ValueError(
                "NumPy 이미지 배열은 2차원 또는 3차원이어야 합니다."
            )

        image_height, image_width = image.shape[:2]
        input_image = image
    else:
        raise TypeError(
            "image는 PIL.Image.Image 또는 numpy.ndarray이어야 합니다."
        )

    model = get_yolo_model()
    results = model.predict(
        source=input_image,
        imgsz=YOLO_IMAGE_SIZE,
        conf=confidence_threshold,
        iou=iou_threshold,
        verbose=False,
    )

    if not results:
        return {
            "image_width": int(image_width),
            "image_height": int(image_height),
            "detection_count": 0,
            "detections": [],
        }

    result = results[0]
    boxes = result.boxes
    detections: list[dict[str, Any]] = []

    if boxes is not None and len(boxes) > 0:
        xyxy_values = boxes.xyxy.detach().cpu().tolist()
        confidence_values = boxes.conf.detach().cpu().tolist()
        class_values = boxes.cls.detach().cpu().tolist()

        for box_index, (
            xyxy,
            confidence,
            class_value,
        ) in enumerate(
            zip(
                xyxy_values,
                confidence_values,
                class_values,
            )
        ):
            x1, y1, x2, y2 = map(float, xyxy)
            class_id = int(class_value)

            class_name = str(
                result.names.get(
                    class_id,
                    f"class_{class_id}",
                )
            )

            normalized_x1 = x1 / image_width
            normalized_y1 = y1 / image_height
            normalized_x2 = x2 / image_width
            normalized_y2 = y2 / image_height

            detections.append(
                {
                    "detection_id": f"det_{box_index}",
                    "detection_index": box_index,
                    "source": "ai",
                    "edit_status": "original",
                    "class_id": class_id,
                    "class_name": class_name,
                    "confidence": round(float(confidence), 6),
                    "box": {
                        "x1": round(x1, 4),
                        "y1": round(y1, 4),
                        "x2": round(x2, 4),
                        "y2": round(y2, 4),
                        "width": round(x2 - x1, 4),
                        "height": round(y2 - y1, 4),
                    },
                    "box_normalized": {
                        "x1": round(normalized_x1, 6),
                        "y1": round(normalized_y1, 6),
                        "x2": round(normalized_x2, 6),
                        "y2": round(normalized_y2, 6),
                        "width": round(
                            normalized_x2 - normalized_x1,
                            6,
                        ),
                        "height": round(
                            normalized_y2 - normalized_y1,
                            6,
                        ),
                    },
                }
            )

    return {
        "image_width": int(image_width),
        "image_height": int(image_height),
        "detection_count": len(detections),
        "detections": detections,
    }
