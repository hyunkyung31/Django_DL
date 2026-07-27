from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


# ---------------------------------------------------------
# 공통 타입
# ---------------------------------------------------------

NormalizedCoordinate = Annotated[
    float,
    Field(
        ge=0.0,
        le=1.0,
        description="좌측 상단 원점을 기준으로 0~1 범위로 정규화된 좌표",
    ),
]

AnnotationId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]

HexColor = Annotated[
    str,
    StringConstraints(
        pattern=r"^#[0-9A-Fa-f]{6}$",
    ),
]


# ---------------------------------------------------------
# 열거형
# ---------------------------------------------------------

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class AnnotationContextMode(str, Enum):
    IMAGE = "image"
    PAUSED_FRAME = "paused_frame"
    BOOKMARK = "bookmark"


class BoundingBoxEditStatus(str, Enum):
    ORIGINAL = "original"
    MODIFIED = "modified"
    DELETED = "deleted"


class FreehandEditStatus(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


# ---------------------------------------------------------
# 좌표 모델
# ---------------------------------------------------------

class NormalizedPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: NormalizedCoordinate
    y: NormalizedCoordinate


class NormalizedBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x1: NormalizedCoordinate
    y1: NormalizedCoordinate
    x2: NormalizedCoordinate
    y2: NormalizedCoordinate

    @model_validator(mode="after")
    def validate_box_order(self) -> "NormalizedBox":
        if self.x1 >= self.x2:
            raise ValueError("x1은 x2보다 작아야 합니다.")

        if self.y1 >= self.y2:
            raise ValueError("y1은 y2보다 작아야 합니다.")

        return self


# ---------------------------------------------------------
# 편집 대상 문맥
# ---------------------------------------------------------

class AnnotationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: AnnotationContextMode

    frame_index: int | None = Field(
        default=None,
        ge=0,
        description="동영상에서 편집 대상이 되는 0부터 시작하는 프레임 번호",
    )

    timestamp_seconds: float | None = Field(
        default=None,
        ge=0.0,
        description="동영상 시작 시점부터 편집 프레임까지의 시간",
    )

    bookmark_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_context(self) -> "AnnotationContext":
        if self.mode == AnnotationContextMode.IMAGE:
            if self.frame_index is not None:
                raise ValueError(
                    "이미지 편집 문맥에는 frame_index를 사용할 수 없습니다."
                )

            if self.timestamp_seconds is not None:
                raise ValueError(
                    "이미지 편집 문맥에는 timestamp_seconds를 사용할 수 없습니다."
                )

            if self.bookmark_id is not None:
                raise ValueError(
                    "이미지 편집 문맥에는 bookmark_id를 사용할 수 없습니다."
                )

        if self.mode in {
            AnnotationContextMode.PAUSED_FRAME,
            AnnotationContextMode.BOOKMARK,
        }:
            if self.frame_index is None:
                raise ValueError(
                    "동영상 프레임 편집에는 frame_index가 필요합니다."
                )

            if self.timestamp_seconds is None:
                raise ValueError(
                    "동영상 프레임 편집에는 timestamp_seconds가 필요합니다."
                )

        if (
            self.mode == AnnotationContextMode.BOOKMARK
            and not self.bookmark_id
        ):
            raise ValueError(
                "bookmark 모드에는 bookmark_id가 필요합니다."
            )

        return self


# ---------------------------------------------------------
# Bounding Box Annotation
# ---------------------------------------------------------

class BoundingBoxAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation_type: Literal["bounding_box"] = "bounding_box"

    annotation_id: AnnotationId

    detection_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="FastAPI AI 탐지 결과의 고유 식별자",
    )

    source: Literal["ai"] = "ai"

    edit_status: BoundingBoxEditStatus

    class_id: int | None = Field(
        default=None,
        ge=0,
    )

    class_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    ai_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    original_box_normalized: NormalizedBox

    edited_box_normalized: NormalizedBox | None = None

    @model_validator(mode="after")
    def validate_edit_status(self) -> "BoundingBoxAnnotation":
        if (
            self.edit_status
            == BoundingBoxEditStatus.ORIGINAL
            and self.edited_box_normalized is not None
        ):
            raise ValueError(
                "original 상태에서는 edited_box_normalized를 사용할 수 없습니다."
            )

        if (
            self.edit_status
            == BoundingBoxEditStatus.MODIFIED
            and self.edited_box_normalized is None
        ):
            raise ValueError(
                "modified 상태에는 edited_box_normalized가 필요합니다."
            )

        if (
            self.edit_status
            == BoundingBoxEditStatus.DELETED
            and self.edited_box_normalized is not None
        ):
            raise ValueError(
                "deleted 상태에서는 edited_box_normalized가 없어야 합니다."
            )

        return self


# ---------------------------------------------------------
# 자유형 펜 Annotation
# ---------------------------------------------------------

class FreehandAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation_type: Literal["freehand"] = "freehand"

    annotation_id: AnnotationId

    source: Literal["user"] = "user"

    edit_status: FreehandEditStatus = FreehandEditStatus.ADDED

    tool: Literal["pen"] = "pen"

    stroke_color: HexColor = "#FF0000"

    stroke_width: float = Field(
        default=3.0,
        gt=0.0,
        le=20.0,
    )

    points_normalized: list[NormalizedPoint] = Field(
        min_length=2,
        max_length=10000,
    )


# ---------------------------------------------------------
# Annotation Union
# ---------------------------------------------------------

AnnotationItem = Annotated[
    Union[
        BoundingBoxAnnotation,
        FreehandAnnotation,
    ],
    Field(discriminator="annotation_type"),
]


# ---------------------------------------------------------
# 좌표 체계 정보
# ---------------------------------------------------------

class CoordinateSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["normalized"] = "normalized"

    range: tuple[Literal[0], Literal[1]] = (0, 1)

    origin: Literal["top_left"] = "top_left"


# ---------------------------------------------------------
# 전체 요청 모델
# ---------------------------------------------------------

class AnnotationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_id: int | None = Field(
        default=None,
        ge=1,
        description="Django 검사 데이터 식별자이며 팀 협의 후 필수 여부 확정",
    )

    analysis_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="FastAPI 분석 실행 식별자이며 팀 협의 후 필수 여부 확정",
    )

    patient_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="검사 정보로 조회 가능하므로 선택값",
    )

    media_type: MediaType

    annotation_context: AnnotationContext

    coordinate_system: CoordinateSystem = Field(
        default_factory=CoordinateSystem
    )

    annotations: list[AnnotationItem] = Field(
        default_factory=list,
        max_length=1000,
    )

    is_finalized: bool = False

    @model_validator(mode="after")
    def validate_request(self) -> "AnnotationRequest":
        if (
            self.media_type == MediaType.IMAGE
            and self.annotation_context.mode
            != AnnotationContextMode.IMAGE
        ):
            raise ValueError(
                "media_type이 image이면 annotation_context.mode도 image여야 합니다."
            )

        if (
            self.media_type == MediaType.VIDEO
            and self.annotation_context.mode
            == AnnotationContextMode.IMAGE
        ):
            raise ValueError(
                "media_type이 video이면 paused_frame 또는 bookmark 모드여야 합니다."
            )

        annotation_ids = [
            annotation.annotation_id
            for annotation in self.annotations
        ]

        if len(annotation_ids) != len(set(annotation_ids)):
            raise ValueError(
                "동일한 요청 안에서 annotation_id는 중복될 수 없습니다."
            )

        return self