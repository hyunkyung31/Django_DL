from fastapi import APIRouter, status

from schemas.annotation import AnnotationRequest


router = APIRouter(
    prefix="/annotations",
    tags=["annotations"],
)


@router.post(
    "/validate",
    status_code=status.HTTP_200_OK,
    summary="Annotation JSON 검증",
)
async def validate_annotation(
    payload: AnnotationRequest,
) -> dict[str, object]:
    """
    Bounding Box 및 자유곡선 Annotation JSON을 검증한다.

    이 API는 데이터를 저장하지 않는다.
    """
    return {
        "success": True,
        "message": "Annotation 데이터 검증에 성공했습니다.",
        "data": payload.model_dump(mode="json"),
    }