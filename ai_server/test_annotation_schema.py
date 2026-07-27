from pprint import pprint

from pydantic import ValidationError

from schemas.annotation import AnnotationRequest


def run_valid_case(name: str, payload: dict) -> None:
    print(f"\n[정상 테스트] {name}")

    try:
        result = AnnotationRequest.model_validate(payload)
        pprint(result.model_dump(mode="json"))
        print("결과: 성공")

    except ValidationError as error:
        print("결과: 실패")
        print(error)


def run_invalid_case(name: str, payload: dict) -> None:
    print(f"\n[오류 테스트] {name}")

    try:
        AnnotationRequest.model_validate(payload)
        print("결과: 실패 - 오류가 발생해야 하지만 통과했습니다.")

    except ValidationError as error:
        print("결과: 성공 - 예상한 검증 오류가 발생했습니다.")
        print(error)


valid_modified_box = {
    "exam_id": 101,
    "analysis_id": "analysis_video_001",
    "patient_id": "P001",
    "media_type": "video",
    "annotation_context": {
        "mode": "paused_frame",
        "frame_index": 125,
        "timestamp_seconds": 10.0,
        "bookmark_id": None,
    },
    "annotations": [
        {
            "annotation_type": "bounding_box",
            "annotation_id": "frame_125_det_0",
            "detection_id": "frame_125_det_0",
            "source": "ai",
            "edit_status": "modified",
            "class_id": 0,
            "class_name": "stenosis",
            "ai_confidence": 0.81,
            "original_box_normalized": {
                "x1": 0.31,
                "y1": 0.42,
                "x2": 0.46,
                "y2": 0.56,
            },
            "edited_box_normalized": {
                "x1": 0.28,
                "y1": 0.39,
                "x2": 0.50,
                "y2": 0.60,
            },
        }
    ],
    "is_finalized": False,
}


valid_deleted_box = {
    "exam_id": 101,
    "analysis_id": "analysis_video_001",
    "media_type": "video",
    "annotation_context": {
        "mode": "bookmark",
        "frame_index": 125,
        "timestamp_seconds": 10.0,
        "bookmark_id": "bookmark_001",
    },
    "annotations": [
        {
            "annotation_type": "bounding_box",
            "annotation_id": "frame_125_det_0",
            "detection_id": "frame_125_det_0",
            "source": "ai",
            "edit_status": "deleted",
            "class_id": 0,
            "class_name": "stenosis",
            "ai_confidence": 0.81,
            "original_box_normalized": {
                "x1": 0.31,
                "y1": 0.42,
                "x2": 0.46,
                "y2": 0.56,
            },
            "edited_box_normalized": None,
        }
    ],
}


valid_freehand = {
    "exam_id": 101,
    "analysis_id": "analysis_video_001",
    "media_type": "video",
    "annotation_context": {
        "mode": "paused_frame",
        "frame_index": 125,
        "timestamp_seconds": 10.0,
    },
    "annotations": [
        {
            "annotation_type": "freehand",
            "annotation_id": "frame_125_pen_001",
            "source": "user",
            "edit_status": "added",
            "tool": "pen",
            "stroke_color": "#FF0000",
            "stroke_width": 3,
            "points_normalized": [
                {"x": 0.31, "y": 0.42},
                {"x": 0.32, "y": 0.43},
                {"x": 0.34, "y": 0.45},
            ],
        }
    ],
}


invalid_out_of_range = {
    **valid_modified_box,
    "annotations": [
        {
            **valid_modified_box["annotations"][0],
            "edited_box_normalized": {
                "x1": -0.1,
                "y1": 0.39,
                "x2": 0.50,
                "y2": 0.60,
            },
        }
    ],
}


invalid_box_order = {
    **valid_modified_box,
    "annotations": [
        {
            **valid_modified_box["annotations"][0],
            "edited_box_normalized": {
                "x1": 0.60,
                "y1": 0.39,
                "x2": 0.50,
                "y2": 0.60,
            },
        }
    ],
}


invalid_modified_without_edited_box = {
    **valid_modified_box,
    "annotations": [
        {
            **valid_modified_box["annotations"][0],
            "edited_box_normalized": None,
        }
    ],
}


invalid_deleted_with_edited_box = {
    **valid_deleted_box,
    "annotations": [
        {
            **valid_deleted_box["annotations"][0],
            "edited_box_normalized": {
                "x1": 0.28,
                "y1": 0.39,
                "x2": 0.50,
                "y2": 0.60,
            },
        }
    ],
}


invalid_freehand_one_point = {
    **valid_freehand,
    "annotations": [
        {
            **valid_freehand["annotations"][0],
            "points_normalized": [
                {"x": 0.31, "y": 0.42},
            ],
        }
    ],
}


invalid_bookmark_without_id = {
    **valid_deleted_box,
    "annotation_context": {
        "mode": "bookmark",
        "frame_index": 125,
        "timestamp_seconds": 10.0,
        "bookmark_id": None,
    },
}


invalid_duplicate_annotation_id = {
    **valid_modified_box,
    "annotations": [
        valid_modified_box["annotations"][0],
        {
            "annotation_type": "freehand",
            "annotation_id": "frame_125_det_0",
            "source": "user",
            "edit_status": "added",
            "tool": "pen",
            "stroke_color": "#FF0000",
            "stroke_width": 3,
            "points_normalized": [
                {"x": 0.40, "y": 0.40},
                {"x": 0.41, "y": 0.41},
            ],
        },
    ],
}


invalid_video_image_context = {
    **valid_modified_box,
    "annotation_context": {
        "mode": "image",
    },
}


def main() -> None:
    run_valid_case(
        "Bounding Box 위치 및 크기 수정",
        valid_modified_box,
    )

    run_valid_case(
        "북마크 프레임 Bounding Box 삭제",
        valid_deleted_box,
    )

    run_valid_case(
        "정지 프레임 자유형 펜 추가",
        valid_freehand,
    )

    run_invalid_case(
        "정규화 좌표 범위 초과",
        invalid_out_of_range,
    )

    run_invalid_case(
        "Bounding Box 좌표 순서 오류",
        invalid_box_order,
    )

    run_invalid_case(
        "수정 상태에서 수정 좌표 누락",
        invalid_modified_without_edited_box,
    )

    run_invalid_case(
        "삭제 상태에서 수정 좌표 존재",
        invalid_deleted_with_edited_box,
    )

    run_invalid_case(
        "자유형 펜 좌표가 한 개뿐인 경우",
        invalid_freehand_one_point,
    )

    run_invalid_case(
        "북마크 모드에서 bookmark_id 누락",
        invalid_bookmark_without_id,
    )

    run_invalid_case(
        "annotation_id 중복",
        invalid_duplicate_annotation_id,
    )

    run_invalid_case(
        "동영상인데 이미지 편집 문맥 사용",
        invalid_video_image_context,
    )


if __name__ == "__main__":
    main()