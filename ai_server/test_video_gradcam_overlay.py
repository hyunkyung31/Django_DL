from __future__ import annotations

import json
import sys
from pathlib import Path

from services.video_service import (
    classify_video_frames,
)


def validate_frame_results(
    frames: list[dict[str, object]],
    processed_frames: int,
) -> dict[str, int]:
    """
    프론트엔드가 사용할 프레임별 분석 결과가
    필요한 필드를 모두 포함하는지 검증한다.

    이 검증을 하는 이유는 FastAPI 실행 자체가 성공하더라도
    frame_index, timestamp_seconds 또는 Grad-CAM 경로가 누락되면
    React에서 영상 재생 시간과 오버레이 이미지를 연결할 수 없기 때문이다.
    """
    if len(frames) != processed_frames:
        raise AssertionError(
            "프레임 결과 개수와 처리된 프레임 수가 일치하지 않습니다: "
            f"{len(frames)} != {processed_frames}"
        )

    required_fields = {
        "frame_index",
        "frame_number",
        "timestamp_seconds",
        "predicted_class",
        "predicted_label",
        "confidence",
        "show_gradcam",
        "gradcam_relative_path",
        "probabilities",
    }

    gradcam_frame_count = 0
    missing_gradcam_file_count = 0

    for expected_index, frame in enumerate(frames):
        # 각 프레임 결과가 딕셔너리인지 확인해야
        # 이후 필드 접근 과정에서 예기치 않은 타입 오류를 방지할 수 있다.
        if not isinstance(frame, dict):
            raise AssertionError(
                f"{expected_index}번째 프레임 결과가 dict가 아닙니다."
            )

        missing_fields = required_fields - frame.keys()

        if missing_fields:
            raise AssertionError(
                f"{expected_index}번째 프레임에 필수 필드가 없습니다: "
                f"{sorted(missing_fields)}"
            )

        # 프레임 순서가 실제 처리 순서와 일치해야
        # React에서 currentTime과 frame_index를 정확히 연결할 수 있다.
        if int(frame["frame_index"]) != expected_index:
            raise AssertionError(
                "frame_index가 처리 순서와 일치하지 않습니다: "
                f"expected={expected_index}, "
                f"actual={frame['frame_index']}"
            )

        # 사용자에게 표시되는 frame_number는 1부터 시작하도록 설계되어 있다.
        if int(frame["frame_number"]) != expected_index + 1:
            raise AssertionError(
                "frame_number가 올바르지 않습니다: "
                f"expected={expected_index + 1}, "
                f"actual={frame['frame_number']}"
            )

        timestamp_seconds = float(
            frame["timestamp_seconds"]
        )

        if timestamp_seconds < 0:
            raise AssertionError(
                "timestamp_seconds는 음수가 될 수 없습니다."
            )

        probabilities = frame["probabilities"]

        if not isinstance(probabilities, dict):
            raise AssertionError(
                f"{expected_index}번째 probabilities가 dict가 아닙니다."
            )

        if (
            "normal" not in probabilities
            or "stenosis" not in probabilities
        ):
            raise AssertionError(
                "probabilities에 normal 또는 stenosis가 없습니다."
            )

        normal_probability = float(
            probabilities["normal"]
        )

        stenosis_probability = float(
            probabilities["stenosis"]
        )

        # Softmax 확률은 각각 0과 1 사이에 있어야 한다.
        if not 0.0 <= normal_probability <= 1.0:
            raise AssertionError(
                "normal 확률이 0과 1 사이가 아닙니다."
            )

        if not 0.0 <= stenosis_probability <= 1.0:
            raise AssertionError(
                "stenosis 확률이 0과 1 사이가 아닙니다."
            )

        gradcam_relative_path = frame.get(
            "gradcam_relative_path"
        )

        if gradcam_relative_path:
            gradcam_frame_count += 1

            # 서비스가 반환한 상대 경로를 실제 출력 폴더 경로로 변환한다.
            gradcam_file_path = (
                Path("outputs")
                / "gradcam"
                / str(gradcam_relative_path)
            )

            # JSON에 경로만 있고 실제 PNG가 없으면
            # React가 gradcam_url을 요청해도 이미지를 표시할 수 없다.
            if not gradcam_file_path.exists():
                missing_gradcam_file_count += 1

    return {
        "gradcam_frame_count": gradcam_frame_count,
        "missing_gradcam_file_count": (
            missing_gradcam_file_count
        ),
    }


def main() -> None:
    """
    실제 동영상으로 프론트 오버레이용 분석 결과를 검증한다.

    실행 예시:
    python test_video_gradcam_overlay.py test_videos/sample.avi
    """
    if len(sys.argv) != 2:
        raise SystemExit(
            "사용법: python test_video_gradcam_overlay.py "
            "<입력영상>"
        )

    input_path = Path(sys.argv[1])

    # 존재하지 않는 경로를 OpenCV에 넘기기 전에
    # 테스트 단계에서 명확한 오류 메시지를 제공한다.
    if not input_path.exists():
        raise FileNotFoundError(
            f"입력 동영상을 찾을 수 없습니다: {input_path}"
        )

    # 실제 /video/classification/data API와 같은 옵션으로 실행한다.
    #
    # output_path=None:
    # 결과 MP4 파일을 만들지 않는다.
    #
    # render_output_video=False:
    # Grad-CAM이 합성된 별도 동영상을 생성하지 않는다.
    #
    # save_gradcam_images=True:
    # React가 영상 위에 표시할 투명 Grad-CAM PNG를 저장한다.
    result = classify_video_frames(
        input_path=input_path,
        output_path=None,
        render_output_video=False,
        save_gradcam_images=True,
    )

    analysis_id = result.get("analysis_id")
    processed_frames = int(
        result["processed_frames"]
    )
    frames = result["frames"]

    # Grad-CAM 저장 모드에서는 분석별 출력 폴더를 구분하기 위해
    # analysis_id가 반드시 생성되어야 한다.
    if not analysis_id:
        raise AssertionError(
            "Grad-CAM 저장 모드인데 analysis_id가 생성되지 않았습니다."
        )

    if processed_frames <= 0:
        raise AssertionError(
            "처리된 프레임 수가 0 이하입니다."
        )

    if not isinstance(frames, list):
        raise AssertionError(
            "frames 결과가 list가 아닙니다."
        )

    validation_result = validate_frame_results(
        frames=frames,
        processed_frames=processed_frames,
    )

    if (
        validation_result[
            "missing_gradcam_file_count"
        ]
        > 0
    ):
        raise AssertionError(
            "JSON에 기록된 Grad-CAM 파일 중 "
            f"{validation_result['missing_gradcam_file_count']}개가 "
            "실제 출력 폴더에 존재하지 않습니다."
        )

    # 결과 MP4를 생성하지 않는 테스트이므로
    # 아래 값들은 False 또는 None이어야 한다.
    if result["rendered_output_video"] is not False:
        raise AssertionError(
            "rendered_output_video가 False가 아닙니다."
        )

    if result["output_path"] is not None:
        raise AssertionError(
            "프론트 오버레이 모드에서 output_path가 생성되었습니다."
        )

    if result["output_size_bytes"] is not None:
        raise AssertionError(
            "프론트 오버레이 모드에서 output_size_bytes가 생성되었습니다."
        )

    summary = {
        "test_result": "success",
        "analysis_id": analysis_id,
        "input_metadata": result["input_metadata"],
        "processed_frames": processed_frames,
        "frame_result_count": len(frames),
        "gradcam_frame_count": validation_result[
            "gradcam_frame_count"
        ],
        "missing_gradcam_file_count": validation_result[
            "missing_gradcam_file_count"
        ],
        "rendered_output_video": result[
            "rendered_output_video"
        ],
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