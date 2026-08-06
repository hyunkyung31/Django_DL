# 이미지 통합, 새로운 생성

from functools import partial
from io import BytesIO
from uuid import uuid4
from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from services.gradcam_service import generate_gradcam
from services.yolo_service import (
    YOLO_CONFIDENCE_THRESHOLD,
    YOLO_IOU_THRESHOLD,
    detect_image,
    get_model_information,
)


router = APIRouter(
    prefix="/analysis",
    tags=["Integrated Analysis"],
)

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
}

MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024

@router.post(
    "/image",
    summary="이미지 통합 분석",
)
async def analyze_image(
    file: UploadFile = File(...),
    confidence_threshold: float = YOLO_CONFIDENCE_THRESHOLD,
    iou_threshold: float = YOLO_IOU_THRESHOLD,
    always_show_gradcam: bool = True,
) -> dict[str, object]:
    """
    업로드된 이미지 한 장에 대해 다음 분석을 수행한다.

    1. InceptionV3 분류
    2. Grad-CAM 생성
    3. YOLO 병변 탐지 (seg 가중치여도 bbox만 사용)
    4. 분석 결과 통합 반환
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="파일 이름이 없습니다.",
        )

    if not 0.0 <= confidence_threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="confidence_threshold는 0 이상 1 이하여야 합니다.",
        )

    if not 0.0 <= iou_threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="iou_threshold는 0 이상 1 이하여야 합니다.",
        )

    try:
        image_bytes = await file.read()

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="업로드된 이미지가 비어 있습니다.",
            )

        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="이미지 파일은 20MB를 초과할 수 없습니다.",
            )

        with Image.open(BytesIO(image_bytes)) as image:
            rgb_image = image.convert("RGB")

        # InceptionV3 분류 + Grad-CAM
        classification_result = await run_in_threadpool(
            partial(
                generate_gradcam,
                image=rgb_image,
                target_class=None,
                alpha=0.45,
                always_show=always_show_gradcam,
            )
        )

        # YOLO 병변 탐지
        detection_result = await run_in_threadpool(
            partial(
                detect_image,
                image=rgb_image,
                confidence_threshold=confidence_threshold,
                iou_threshold=iou_threshold,
            )
        )

        return {
            "message": "이미지 통합 분석이 완료되었습니다.",
            "analysis_id": uuid4().hex,
            "original_filename": file.filename,
            "classification": classification_result,
            "detection": detection_result,
        }

    except HTTPException:
        raise

    except UnidentifiedImageError as error:
        raise HTTPException(
            status_code=400,
            detail="올바른 이미지 파일이 아닙니다.",
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"이미지 통합 분석 중 오류가 발생했습니다: {error}",
        ) from error

    finally:
        await file.close()
