from __future__ import annotations

# FastAPI의 라우터 기능을 사용해 Health API를 별도 모듈로 관리한다.
from fastapi import APIRouter

# InceptionV3 서비스가 서버 시작 시 로딩한 모델 객체와
# 가중치 경로, 실행 장치를 가져온다.
from services.inception_service import (
    DEVICE as INCEPTION_DEVICE,
    MODEL_PATH as INCEPTION_MODEL_PATH,
    inception_model,
)

# YOLO 서비스가 서버 시작 시 로딩한 모델 객체와
# 가중치 경로, 모델 정보를 가져온다.
from services.yolo_service import (
    MODEL_PATH as YOLO_MODEL_PATH,
    get_model_information,
    yolo_model,
)


router = APIRouter(
    tags=["Health"],
)


@router.get(
    "/health",
    summary="AI 추론 서버와 모델 상태 확인",
)
def health_check() -> dict[str, object]:
    """
    FastAPI 서버와 InceptionV3·YOLO 모델의 준비 상태를 반환한다.

    목적:
        서버 프로세스만 실행된 상태와 실제 모델 추론이 가능한 상태를
        구분하여 프론트엔드와 배포 환경에서 장애를 빠르게 확인한다.

    주의:
        이 함수는 Health 요청마다 모델을 다시 로드하지 않고,
        서비스 모듈이 시작 시 이미 로드한 모델 객체만 확인한다.
    """

    # InceptionV3 모델 객체가 생성되어 있고
    # 가중치 파일도 실제로 존재하는지 각각 확인한다.
    inception_weights_exist = (
        INCEPTION_MODEL_PATH.is_file()
    )

    inception_model_loaded = (
        inception_model is not None
    )

    # YOLO 모델 객체가 생성되어 있고
    # 가중치 파일도 실제로 존재하는지 각각 확인한다.
    yolo_weights_exist = (
        YOLO_MODEL_PATH.is_file()
    )

    yolo_model_loaded = (
        yolo_model is not None
    )

    # 두 모델과 두 가중치가 모두 준비된 경우에만
    # 전체 추론 서버 상태를 ready로 판단한다.
    models_ready = all(
        [
            inception_weights_exist,
            inception_model_loaded,
            yolo_weights_exist,
            yolo_model_loaded,
        ]
    )

    # 가중치가 없어도 health는 200을 주고, YOLO 준비 여부만 표시한다.
    yolo_information = get_model_information()

    return {
        # 서버 자체는 이 응답을 반환할 수 있으므로 running 상태다.
        "status": "ok",

        # 두 모델 모두 즉시 추론 가능한 상태인지 나타낸다.
        "models_ready": models_ready,

        # 현재 InceptionV3가 CPU 또는 CUDA 중 어느 장치를 사용하는지 표시한다.
        "device": str(INCEPTION_DEVICE),

        "models": {
            "inception_v3": {
                "loaded": inception_model_loaded,
                "weights_exist": (
                    inception_weights_exist
                ),
                "weights_filename": (
                    INCEPTION_MODEL_PATH.name
                ),
                "class_names": {
                    "0": "Normal",
                    "1": "Stenosis",
                },
            },
            "yolo": {
                "loaded": bool(yolo_information.get("loaded")),
                "weights_exist": (
                    yolo_weights_exist
                ),
                "weights_filename": (
                    YOLO_MODEL_PATH.name
                ),
                "task": yolo_information.get("task"),
                "class_count": (
                    yolo_information.get("class_count", 0)
                ),
                "class_names": (
                    yolo_information.get("class_names", {})
                ),
                "image_size": (
                    yolo_information.get("image_size")
                ),
                "detail": yolo_information.get("detail"),
            },
        },
    }