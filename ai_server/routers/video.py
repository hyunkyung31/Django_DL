from __future__ import annotations
import os
from pathlib import Path
from fastapi import (APIRouter, File, HTTPException, Request, UploadFile,)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from services.video_service import (VideoProcessingError,
                                    analyze_video_frames, # Inception,YOLO 통합함수
                                    classify_video_frames,
                                    copy_video_frames,
                                    create_output_path,
                                    create_upload_path,
                                    detect_video_frames,
)
from uuid import uuid4


router = APIRouter(
    prefix="/video",
    tags=["Video"],
)


ALLOWED_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
}

ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/x-msvideo",
    "video/avi",
    "video/quicktime",
    "video/x-matroska",
    "application/octet-stream",
}

MAX_UPLOAD_SIZE_BYTES = int(
    os.environ.get(
        "VIDEO_MAX_UPLOAD_SIZE_BYTES",
        str(500 * 1024 * 1024),
    )
)

# 동영상 업로드 공통 검증 및 임시 저장
def validate_video_file(file: UploadFile) -> None:
    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "지원하지 않는 동영상 확장자입니다. "
                "MP4, AVI, MOV, MKV 파일만 업로드할 수 있습니다."
            ),
        )
    if (
        file.content_type
        and file.content_type not in ALLOWED_CONTENT_TYPES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "지원하지 않는 동영상 Content-Type입니다: "
                f"{file.content_type}"
            ),
        )


def save_upload_file(
    upload_file: UploadFile,
    destination: Path,
) -> int:
    """
    동영상을 메모리 전체에 올리지 않고 일정 크기씩 디스크에 저장한다.
    """
    total_size = 0
    chunk_size = 1024 * 1024

    with destination.open("wb") as output_file:
        while True:
            chunk = upload_file.file.read(chunk_size)

            if not chunk:
                break

            total_size += len(chunk)

            if total_size > MAX_UPLOAD_SIZE_BYTES:
                output_file.close()
                destination.unlink(missing_ok=True)

                raise HTTPException(
                    status_code=413,
                    detail=(
                        "업로드 가능한 최대 동영상 크기를 초과했습니다. "
                        f"현재 제한은 "
                        f"{MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB입니다."
                    ),
                )

            output_file.write(chunk)

    if total_size == 0:
        destination.unlink(missing_ok=True)

        raise HTTPException(
            status_code=400,
            detail="업로드된 동영상 파일이 비어 있습니다.",)

    return total_size


# 동영상 디코딩 및 MP4 출력 파이프라인 테스트
@router.post(
    "/pipeline",
    summary="동영상 입출력 파이프라인 테스트",
)
async def run_video_pipeline(
    file: UploadFile = File(...),
):
    validate_video_file(file)

    input_path = create_upload_path(file.filename)
    output_path = create_output_path()

    try:
        await run_in_threadpool(
            save_upload_file,
            file,
            input_path,
        )

        result = await run_in_threadpool(
            copy_video_frames,
            input_path,
            output_path,
        )

    except HTTPException:
        output_path.unlink(missing_ok=True)
        raise

    except VideoProcessingError as error:
        output_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        output_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=500,
            detail=(
                "동영상 입출력 처리 중 예상하지 못한 오류가 "
                f"발생했습니다: {error}"
            ),
        ) from error

    finally:
        await file.close()
        input_path.unlink(missing_ok=True)

    metadata = result["input_metadata"]

    response = FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=(
            f"{Path(file.filename or 'video').stem}"
            "_processed.mp4"
        ),
    )

    response.headers["X-Video-FPS"] = str(metadata["fps"])
    response.headers["X-Video-Width"] = str(metadata["width"])
    response.headers["X-Video-Height"] = str(metadata["height"])
    response.headers["X-Video-Frame-Count"] = str(
        metadata["frame_count"]
    )
    response.headers["X-Processed-Frame-Count"] = str(
        result["processed_frames"]
    )

    return response

# 동영상 InceptionV3 분류 및 Grad-CAM 데이터 API
@router.post(
    "/classification/data",
    summary="동영상 프레임별 InceptionV3 분석 데이터 생성",
)
async def classify_video_data(
    request: Request,
    file: UploadFile = File(...),
):
    """
    결과 MP4를 생성하지 않고 프론트엔드에서 사용할
    프레임별 InceptionV3 분석 JSON과 Grad-CAM URL을 반환한다.
    """
    validate_video_file(file)

    input_path = create_upload_path(file.filename)

    try:
        await run_in_threadpool(
            save_upload_file,
            file,
            input_path,
        )

        result = await run_in_threadpool(
            classify_video_frames,
            input_path, # 업로드한 임시 동영상 경로
            None, # outputpath 없음
            False, # render_output_video 
            True, # save_gradcam_images
        )

        frames = result["frames"]

        if not isinstance(frames, list):
            raise VideoProcessingError(
                "프레임 분석 결과 형식이 올바르지 않습니다."
            )

        for frame_result in frames:
            if not isinstance(frame_result, dict):
                continue

            relative_path = frame_result.get(
                "gradcam_relative_path"
            )
            frame_result["gradcam_available"] = bool(relative_path)

            if relative_path:
                frame_result["gradcam_url"] = str(
                    request.url_for(
                        "output_gradcam",
                        path=relative_path,
                    )
                )
            else:
                frame_result["gradcam_url"] = None

    except HTTPException:
        raise

    except VideoProcessingError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "동영상 분석 데이터 생성 중 "
                "예상하지 못한 오류가 "
                f"발생했습니다: {error}"
            ),
        ) from error

    finally:
        await file.close()
        input_path.unlink(missing_ok=True)

    return {
        "message": (
            "동영상 프레임별 분석 데이터와 Grad-CAM 생성이 완료되었습니다."
        ),
        "original_filename": file.filename,
        "analysis_id": result["analysis_id"],
        "rendered_output_video": result["rendered_output_video"],
        "result_video_path": None,
        "result_video_url": None,
        "metadata": result["input_metadata"],
        "processed_frames": result["processed_frames"],
        "video_summary": result["video_summary"],
        "frame_summary": result["frame_summary"],
        "frames": result["frames"],
    }
    

# 동영상 프레임별 YOLO 탐지 API
@router.post(
    "/detection/data",
    summary="동영상 프레임별 YOLO 탐지 데이터 생성",
)
async def detect_video_data(
    file: UploadFile = File(...),
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
) -> dict[str, object]:
    """
    업로드한 동영상의 모든 프레임에서 YOLO 탐지를 수행하고
    프레임별 Bounding Box JSON을 반환한다.

    결과 MP4는 생성하지 않는다.
    """
    validate_video_file(file)

    if not 0.0 <= confidence_threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail=(
                "confidence_threshold는 "
                "0 이상 1 이하이어야 합니다."
            ),
        )

    if not 0.0 <= iou_threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail=(
                "iou_threshold는 "
                "0 이상 1 이하이어야 합니다."
            ),
        )

    original_filename = file.filename
    analysis_id = uuid4().hex
    input_path = create_upload_path(original_filename)

    try:
        await run_in_threadpool(
            save_upload_file,
            file,
            input_path,
        )

        result = await run_in_threadpool(
            detect_video_frames,
            input_path,
            confidence_threshold,
            iou_threshold,
        )

    except HTTPException:
        raise

    except VideoProcessingError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "동영상 YOLO 탐지 중 오류가 발생했습니다: "
                f"{error}"
            ),
        ) from error

    finally:
        await file.close()
        input_path.unlink(missing_ok=True)
        
        
    
    return {
        "message": (
            "동영상 프레임별 YOLO 탐지 데이터 생성이 완료되었습니다."
        ),
        "analysis_id": analysis_id,
        "original_filename": original_filename,
        "editable": True,
        "coordinate_system": {
            "pixel_format": "xyxy",
            "normalized_format": "xyxy",
            "normalized_range": [0.0, 1.0],
            "origin": "top_left",
        },
        **result,
    }
    
    
 # InceptionV3·Grad-CAM·YOLO 통합 동영상 분석 API
@router.post(
    "/analyze",
    summary="동영상 통합 AI 분석",
)
async def analyze_video_data(
    request: Request,
    file: UploadFile = File(...),
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
) -> dict[str, object]:
    """
    업로드한 동영상을 한 번만 순회하면서
    InceptionV3 분류·Grad-CAM과 YOLO 탐지를 함께 수행한다.

    React에서 원본 영상 위에 Grad-CAM과 Bounding Box를
    독립적으로 표시할 수 있도록 프레임별 통합 JSON을 반환한다.
    """
    validate_video_file(file)

    if not 0.0 <= confidence_threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail=(
                "confidence_threshold는 "
                "0 이상 1 이하이어야 합니다."
            ),
        )

    if not 0.0 <= iou_threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail=(
                "iou_threshold는 "
                "0 이상 1 이하이어야 합니다."
            ),
        )

    original_filename = file.filename
    input_path = create_upload_path(original_filename)

    try:
        # 업로드된 동영상을 메모리에 모두 올리지 않고
        # 임시 파일로 저장한다.
        await run_in_threadpool(
            save_upload_file,
            file,
            input_path,
        )

        # 같은 동영상 프레임을 한 번만 읽으면서
        # InceptionV3·Grad-CAM과 YOLO를 함께 실행한다.
        result = await run_in_threadpool(
            analyze_video_frames,
            input_path,
            confidence_threshold,
            iou_threshold,
            True,
        )

        frames = result["frames"]

        if not isinstance(frames, list):
            raise VideoProcessingError(
                "통합 프레임 결과 형식이 올바르지 않습니다."
            )

        # 서비스에서는 파일 시스템 기준 상대 경로만 생성하므로,
        # Request 객체가 있는 라우터에서 공개 URL로 변환한다.
        for frame_result in frames:
            if not isinstance(frame_result, dict):
                raise VideoProcessingError(
                    "통합 프레임 항목 형식이 올바르지 않습니다."
                )

            gradcam_result = frame_result.get(
                "gradcam"
            )

            if not isinstance(gradcam_result, dict):
                raise VideoProcessingError(
                    "Grad-CAM 결과 형식이 올바르지 않습니다."
                )

            relative_path = gradcam_result.get(
                "relative_path"
            )

            gradcam_result["available"] = bool(
                relative_path
            )

            if relative_path:
                gradcam_result["url"] = str(
                    request.url_for(
                        "output_gradcam",
                        path=str(relative_path),
                    )
                )
            else:
                gradcam_result["url"] = None

    except HTTPException:
        raise

    except VideoProcessingError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "동영상 통합 AI 분석 중 예상하지 못한 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    finally:
        await file.close()
        input_path.unlink(missing_ok=True)

    return {
        "message": (
            "동영상 통합 AI 분석이 완료되었습니다."
        ),
        "original_filename": original_filename,
        "analysis_id": result["analysis_id"],
        "metadata": result["input_metadata"],
        "processed_frames": (
            result["processed_frames"]
        ),

        # video_service.py에서 측정한 전체 처리 시간과
        # 프레임당 처리 속도를 그대로 전달한다.
        "performance": result["performance"],

        "rendered_output_video": (
            result["rendered_output_video"]
        ),
        "result_video_path": None,
        "result_video_url": None,
        "classification_summary": (
            result["classification_summary"]
        ),
        "classification_frame_summary": (
            result["classification_frame_summary"]
        ),
        "detection_summary": (
            result["detection_summary"]
        ),
        "confidence_threshold": (
            result["confidence_threshold"]
        ),
        "iou_threshold": result["iou_threshold"],
        "editable": True,
        "coordinate_system": {
            "pixel_format": "xyxy",
            "normalized_format": "xyxy",
            "normalized_range": [0.0, 1.0],
            "origin": "top_left",
        },
        "frames": frames,
    }
