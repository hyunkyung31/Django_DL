from services.annotation_mapper import (
    map_yolo_detections_to_annotations,
)


def test_detected_frame_annotations() -> None:
    detections = [
        {
            "detection_id": "frame_40_det_0",
            "detection_index": 0,
            "source": "ai",
            "edit_status": "original",
            "class_id": 0,
            "class_name": "Lesion",
            "confidence": 0.603294,
            "box_normalized": {
                "x1": 0.627126,
                "y1": 0.590411,
                "x2": 0.770497,
                "y2": 0.72374,
                "width": 0.143372,
                "height": 0.133329,
            },
        }
    ]

    annotations = map_yolo_detections_to_annotations(
        detections,
        media_type="video",
        frame_index=40,
    )

    assert len(annotations) == 1

    annotation = annotations[0]

    assert annotation["annotation_id"] == "frame_40_det_0"
    assert annotation["detection_id"] == "frame_40_det_0"
    assert annotation["annotation_type"] == "bounding_box"
    assert annotation["source"] == "ai"
    assert annotation["edit_status"] == "original"
    assert annotation["class_id"] == 0
    assert annotation["class_name"] == "Lesion"
    assert annotation["ai_confidence"] == 0.603294

    assert annotation["original_box_normalized"] == {
        "x1": 0.627126,
        "y1": 0.590411,
        "x2": 0.770497,
        "y2": 0.72374,
    }

    assert annotation["edited_box_normalized"] is None


def test_empty_frame_annotations() -> None:
    annotations = map_yolo_detections_to_annotations(
        [],
        media_type="video",
        frame_index=44,
    )

    assert annotations == []


def test_frame_ids_are_unique() -> None:
    detections = [
        {
            "detection_id": "frame_39_det_0",
            "detection_index": 0,
            "class_id": 0,
            "class_name": "Lesion",
            "confidence": 0.560063,
            "box_normalized": {
                "x1": 0.125096,
                "y1": 0.483482,
                "x2": 0.544453,
                "y2": 0.609824,
            },
        },
        {
            "detection_id": "frame_39_det_1",
            "detection_index": 1,
            "class_id": 0,
            "class_name": "Lesion",
            "confidence": 0.338246,
            "box_normalized": {
                "x1": 0.602174,
                "y1": 0.59805,
                "x2": 0.988804,
                "y2": 0.738035,
            },
        },
    ]

    annotations = map_yolo_detections_to_annotations(
        detections,
        media_type="video",
        frame_index=39,
    )

    annotation_ids = [
        annotation["annotation_id"]
        for annotation in annotations
    ]

    assert annotation_ids == [
        "frame_39_det_0",
        "frame_39_det_1",
    ]

    assert len(annotation_ids) == len(set(annotation_ids))


def test_video_requires_frame_index() -> None:
    detections = [
        {
            "detection_id": "det_0",
            "detection_index": 0,
            "class_id": 0,
            "class_name": "Lesion",
            "confidence": 0.5,
            "box_normalized": {
                "x1": 0.1,
                "y1": 0.1,
                "x2": 0.2,
                "y2": 0.2,
            },
        }
    ]

    try:
        map_yolo_detections_to_annotations(
            detections,
            media_type="video",
            frame_index=None,
        )
    except ValueError as error:
        assert "frame_index" in str(error)
    else:
        raise AssertionError(
            "동영상 변환에서 frame_index 누락을 허용했습니다."
        )


def main() -> None:
    test_detected_frame_annotations()
    print("탐지 프레임 Annotation 테스트 성공")

    test_empty_frame_annotations()
    print("빈 프레임 Annotation 테스트 성공")

    test_frame_ids_are_unique()
    print("프레임 Annotation ID 테스트 성공")

    test_video_requires_frame_index()
    print("frame_index 필수 검증 테스트 성공")

    print("모든 동영상 Annotation 테스트 성공")


if __name__ == "__main__":
    main()