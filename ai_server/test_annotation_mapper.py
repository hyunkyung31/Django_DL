# YOLO 응답 형태 변환 테스트
from pprint import pprint

from services.annotation_mapper import (
    map_yolo_detections_to_annotations,
    normalized_box_to_pixel,
    pixel_box_to_normalized,
)


sample_detections = [
    {
        "detection_id": "det_0",
        "detection_index": 0,
        "source": "ai",
        "edit_status": "original",
        "class_id": 0,
        "class_name": "Lesion",
        "confidence": 0.422551,
        "box": {
            "x1": 205.1198,
            "y1": 55.823,
            "x2": 437.5107,
            "y2": 173.9891,
            "width": 232.3909,
            "height": 118.1661,
        },
        "box_normalized": {
            "x1": 0.400625,
            "y1": 0.109029,
            "x2": 0.854513,
            "y2": 0.339822,
            "width": 0.453888,
            "height": 0.230793,
        },
    }
]


def main() -> None:
    print("\n[이미지 Annotation 변환]")

    image_annotations = map_yolo_detections_to_annotations(
        sample_detections,
        media_type="image",
    )

    pprint(image_annotations)

    assert image_annotations[0]["annotation_id"] == "image_det_0"
    assert image_annotations[0]["detection_id"] == "det_0"
    assert image_annotations[0]["edit_status"] == "original"
    assert image_annotations[0]["ai_confidence"] == 0.422551
    assert (
        image_annotations[0]["original_box_normalized"]["x1"]
        == 0.400625
    )
    assert (
        image_annotations[0]["edited_box_normalized"]
        is None
    )

    print("이미지 Annotation 변환 성공")

    print("\n[동영상 Annotation 변환]")

    video_annotations = map_yolo_detections_to_annotations(
        sample_detections,
        media_type="video",
        frame_index=125,
    )

    pprint(video_annotations)

    assert (
        video_annotations[0]["annotation_id"]
        == "frame_125_det_0"
    )
    assert (
        video_annotations[0]["detection_id"]
        == "frame_125_det_0"
    )

    print("동영상 Annotation 변환 성공")

    print("\n[픽셀 좌표 → 정규화 좌표]")

    normalized = pixel_box_to_normalized(
        x1=128,
        y1=64,
        x2=256,
        y2=192,
        image_width=512,
        image_height=512,
    )

    pprint(normalized)

    assert normalized == {
        "x1": 0.25,
        "y1": 0.125,
        "x2": 0.5,
        "y2": 0.375,
    }

    print("픽셀 좌표 정규화 성공")

    print("\n[정규화 좌표 → 픽셀 좌표]")

    pixel = normalized_box_to_pixel(
        **normalized,
        image_width=512,
        image_height=512,
    )

    pprint(pixel)

    assert pixel == {
        "x1": 128.0,
        "y1": 64.0,
        "x2": 256.0,
        "y2": 192.0,
    }

    print("정규화 좌표 역변환 성공")

    print("\n모든 Annotation Mapper 테스트 성공")


if __name__ == "__main__":
    main()