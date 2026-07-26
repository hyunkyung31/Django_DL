from __future__ import annotations

import json
import sys
from pathlib import Path

from services.video_service import (
    classify_video_frames,
    create_output_path,
)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "사용법: python test_video_classification.py "
            "<입력영상>"
        )

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        raise FileNotFoundError(
            f"입력 동영상을 찾을 수 없습니다: {input_path}"
        )

    output_path = create_output_path()

    result = classify_video_frames(
        input_path=input_path,
        output_path=output_path,
    )

    summary = {
        "input_metadata": result["input_metadata"],
        "processed_frames": result["processed_frames"],
        "output_path": result["output_path"],
        "video_summary": result["video_summary"],
        "frame_summary": result["frame_summary"],
    }

    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()