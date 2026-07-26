from pathlib import Path
import sys

from services.video_service import (
    VideoProcessingError,
    detect_video_frames,
)


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "사용법: "
            "python test_video_yolo_detection.py "
            "<동영상_경로>"
        )
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(
            f"동영상 파일을 찾을 수 없습니다: "
            f"{input_path}"
        )
        sys.exit(1)

    try:
        result = detect_video_frames(
            input_path=input_path,
            confidence_threshold=0.25,
            iou_threshold=0.45,
        )

    except (
        VideoProcessingError,
        ValueError,
        OSError,
    ) as error:
        print(
            f"YOLO 동영상 탐지 중 오류가 발생했습니다: "
            f"{error}"
        )
        sys.exit(1)

    metadata = result["input_metadata"]
    summary = result["detection_summary"]

    print("===== YOLO Video Detection =====")
    print(f"FPS                  : {metadata['fps']}")
    print(
        f"Resolution           : "
        f"{metadata['width']}x{metadata['height']}"
    )
    print(
        f"Metadata Frame Count : "
        f"{metadata['frame_count']}"
    )
    print(
        f"Processed Frames     : "
        f"{result['processed_frames']}"
    )
    print(
        f"Detected Frames      : "
        f"{summary['detected_frame_count']}"
    )
    print(
        f"Total Detections     : "
        f"{summary['total_detection_count']}"
    )

    highest = summary[
        "highest_confidence_detection"
    ]

    if highest is None:
        print("탐지된 병변 후보가 없습니다.")
        return

    print()
    print("===== Highest Confidence Detection =====")
    print(f"Frame Index : {highest['frame_index']}")
    print(f"Frame Number: {highest['frame_number']}")
    print(
        f"Timestamp   : "
        f"{highest['timestamp_seconds']}"
    )
    print(f"Class       : {highest['class_name']}")
    print(f"Confidence  : {highest['confidence']}")
    print(f"Box         : {highest['box']}")


if __name__ == "__main__":
    main()