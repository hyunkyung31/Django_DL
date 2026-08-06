from io import BytesIO
from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from services.yolo_service import (
    YOLO_CONFIDENCE_THRESHOLD,
    YOLO_IOU_THRESHOLD,
    detect_image,
    get_model_information,
)
from uuid import uuid4
from services.annotation_mapper import (map_yolo_detections_to_annotations,)

router = APIRouter(
    prefix="/yolo",
    tags=["YOLO Detection"],
)

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
}

MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024


@router.get("/model-info")
async def get_yolo_model_info() -> dict[str, object]:
    """
    현재 로딩된 YOLO 탐지 모델의 정보를 반환한다.
    """
    return get_model_information()


@router.post("/detect")
async def detect_yolo_image(
    file: UploadFile = File(...),
    confidence_threshold: float = YOLO_CONFIDENCE_THRESHOLD,
    iou_threshold: float = YOLO_IOU_THRESHOLD,
) -> dict[str, object]:
    """
    업로드한 이미지에서 병변 Bounding Box를 탐지한다.

    segment 가중치여도 mask는 사용하지 않고 bbox만 반환한다.
    """
    analysis_id = uuid4().hex # 요청할 때마다 새 analysis_id 생성
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="파일 이름이 없습니다.",
        )

    filename_lower = file.filename.lower()

    if not any(
        filename_lower.endswith(extension)
        for extension in ALLOWED_IMAGE_EXTENSIONS
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "지원하지 않는 이미지 형식입니다. "
                "jpg, jpeg, png, bmp, webp 형식만 가능합니다."
            ),
        )

    if not 0.0 <= confidence_threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="confidence_threshold는 0 이상 1 이하이어야 합니다.",
        )

    if not 0.0 <= iou_threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="iou_threshold는 0 이상 1 이하이어야 합니다.",
        )

    try:
        image_bytes = await file.read()

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="업로드된 이미지 파일이 비어 있습니다.",
            )

        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="이미지 파일 크기는 20MB를 초과할 수 없습니다.",
            )

        with Image.open(BytesIO(image_bytes)) as image:
            rgb_image = image.convert("RGB")

        result = await run_in_threadpool(
            detect_image,
            rgb_image,
            confidence_threshold,
            iou_threshold,
        )
        annotations = map_yolo_detections_to_annotations(
            result["detections"],
            media_type="image",
        )

        
        
        return {
            "message": "YOLO 이미지 탐지가 완료되었습니다.",
            "analysis_id": analysis_id,
            "original_filename": file.filename,
            "model": get_model_information(),
            "editable": True,
            "coordinate_system": {
                "pixel_format": "xyxy",
                "normalized_format": "xyxy",
                "normalized_range": [0.0, 1.0],
                "origin": "top_left",
            },
            **result,
            "annotations":annotations,
        }



    except HTTPException:
        raise

    except UnidentifiedImageError as error:
        raise HTTPException(
            status_code=400,
            detail="이미지 파일을 읽을 수 없습니다.",
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"YOLO 이미지 탐지 중 오류가 발생했습니다: {error}",
        ) from error

    finally:
        await file.close()