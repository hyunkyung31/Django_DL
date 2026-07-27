from pathlib import Path
import sys

import cv2


def read_metadata(path: Path) -> dict[str, float | int]:
    capture = cv2.VideoCapture(str(path))

    try:
        if not capture.isOpened():
            raise RuntimeError(
                f"동영상을 열 수 없습니다: {path}"
            )

        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        return {
            "fps": fps,
            "width": width,
            "height": height,
            "frame_count": frame_count,
            "duration_seconds": (
                frame_count / fps if fps > 0 else 0
            ),
        }

    finally:
        capture.release()


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "사용법: python test_video_pipeline.py "
            "<입력영상> <출력영상>"
        )

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    input_metadata = read_metadata(input_path)
    output_metadata = read_metadata(output_path)

    print("입력 동영상")
    print(input_metadata)

    print("\n출력 동영상")
    print(output_metadata)

    print("\n검증 결과")
    print(
        "FPS 일치:",
        abs(
            float(input_metadata["fps"])
            - float(output_metadata["fps"])
        ) < 0.1,
    )
    print(
        "해상도 일치:",
        (
            input_metadata["width"]
            == output_metadata["width"]
            and input_metadata["height"]
            == output_metadata["height"]
        ),
    )
    print(
        "프레임 수 일치:",
        (
            input_metadata["frame_count"]
            == output_metadata["frame_count"]
        ),
    )


if __name__ == "__main__":
    main()