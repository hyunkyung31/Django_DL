from pathlib import Path
import sys

from PIL import Image

from services.yolo_service import detect_image


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "사용법: "
            "python test_yolo_detection.py <이미지_경로>"
        )
        sys.exit(1)

    image_path = Path(sys.argv[1])

    if not image_path.exists():
        print(f"이미지 파일을 찾을 수 없습니다: {image_path}")
        sys.exit(1)

    try:
        with Image.open(image_path) as image:
            result = detect_image(image)

        print("===== YOLO Detection Result =====")
        print(f"Image Width     : {result['image_width']}")
        print(f"Image Height    : {result['image_height']}")
        print(f"Detection Count : {result['detection_count']}")

        detections = result["detections"]

        if not detections:
            print("탐지된 병변이 없습니다.")
            return

        for detection in detections:
            print()
            print(
                f"Detection Index : "
                f"{detection['detection_index']}"
            )
            print(
                f"Class           : "
                f"{detection['class_name']}"
            )
            print(
                f"Confidence      : "
                f"{detection['confidence']}"
            )
            print(
                f"Box             : "
                f"{detection['box']}"
            )
            print(
                f"Normalized Box  : "
                f"{detection['box_normalized']}"
            )

    except Exception as error:
        print(f"YOLO 탐지 중 오류가 발생했습니다: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()