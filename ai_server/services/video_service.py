from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4
import cv2
from PIL import Image
from services.gradcam_service import generate_gradcam_data
import numpy as np
from services.yolo_service import (
    YOLO_CONFIDENCE_THRESHOLD,
    YOLO_IOU_THRESHOLD,
    detect_image,
)
from services.annotation_mapper import (map_yolo_detections_to_annotations,)
from time import perf_counter # 코드 실행 시간 측정 함수


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads" / "videos"
OUTPUT_DIR = BASE_DIR / "outputs" / "videos"
GRADCAM_OUTPUT_DIR = BASE_DIR / "outputs" / "gradcam"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GRADCAM_OUTPUT_DIR.mkdir(parents = True, exist_ok = True,)


@dataclass(frozen=True)
class VideoMetadata:
    fps: float
    width: int
    height: int
    frame_count: int
    duration_seconds: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


class VideoProcessingError(RuntimeError):
    """동영상 읽기 또는 출력 과정에서 발생한 오류."""


# 업로드·출력·Grad-CAM 저장 경로 생성
def create_upload_path(original_filename: str | None) -> Path:
    """
    업로드 파일을 저장할 충돌 없는 임시 경로를 생성한다.
    사용자가 보낸 원본 파일명은 확장자 확인에만 사용한다.
    """
    suffix = Path(original_filename or "").suffix.lower()

    if not suffix:
        suffix = ".mp4"

    return UPLOAD_DIR / f"{uuid4().hex}{suffix}"


def create_output_path() -> Path:
    """처리 결과를 저장할 고유한 MP4 경로를 생성한다."""
    return OUTPUT_DIR / f"{uuid4().hex}_processed.mp4"

def create_gradcam_analysis_directory(
) -> tuple[str, Path]:
    """
    한 번의 동영상 분석 요청에서 생성되는
    Grad-CAM 이미지들을 저장할 고유 폴더를 생성한다.
    """
    analysis_id = uuid4().hex

    analysis_directory = (
        GRADCAM_OUTPUT_DIR / analysis_id
    )

    analysis_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    return analysis_id, analysis_directory


# OpenCV 기반 동영상 메타데이터 검증
def read_video_metadata(video_path: Path) -> VideoMetadata:
    """
    OpenCV로 동영상을 열어 FPS, 해상도, 프레임 수와 재생시간을 확인한다.
    """
    capture = cv2.VideoCapture(str(video_path))

    try:
        if not capture.isOpened():
            raise VideoProcessingError(
                "동영상 파일을 열 수 없습니다."
            )

        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        if fps <= 0:
            raise VideoProcessingError(f"올바른 FPS를 읽을 수 없습니다: {fps}")

        if width <= 0 or height <= 0:
            raise VideoProcessingError( f"올바른 영상 해상도를 읽을 수 없습니다: "
                                        f"{width}x{height}" )

        if frame_count <= 0:
            raise VideoProcessingError(f"올바른 프레임 수를 읽을 수 없습니다: {frame_count}")

        duration_seconds = frame_count / fps

        return VideoMetadata(
            fps=fps,
            width=width,
            height=height,
            frame_count=frame_count,
            duration_seconds=duration_seconds,
        )

    finally:
        capture.release()


def copy_video_frames(
    input_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """
    입력 동영상의 모든 프레임을 읽어 동일한 FPS와 해상도로 MP4에 기록한다.

    현재 단계에서는 AI 추론이나 Grad-CAM 처리를 하지 않는다.
    """
    metadata = read_video_metadata(input_path)

    capture = cv2.VideoCapture(str(input_path))

    if not capture.isOpened():
        raise VideoProcessingError("프레임 처리를 위해 동영상을 다시 열 수 없습니다.")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    writer = cv2.VideoWriter(
        str(output_path),
        fourcc,
        metadata.fps,
        (metadata.width, metadata.height),
    )

    if not writer.isOpened():
        capture.release()

        raise VideoProcessingError("결과 MP4 파일을 생성할 수 없습니다.")

    processed_frames = 0

    try:
        while True:
            success, frame = capture.read()

            if not success:
                break

            if frame is None:
                raise VideoProcessingError(f"{processed_frames}번째 이후 프레임을 읽지 못했습니다.")

            frame_height, frame_width = frame.shape[:2]

            if (frame_width != metadata.width
                or frame_height != metadata.height
            ):
                frame = cv2.resize(frame,
                    (metadata.width, metadata.height),
                    interpolation=cv2.INTER_AREA,
                )

            writer.write(frame)
            processed_frames += 1

    finally:
        capture.release()
        writer.release()

    if processed_frames == 0:
        output_path.unlink(missing_ok=True)

        raise VideoProcessingError("처리된 프레임이 없습니다.")

    if not output_path.exists() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)

        raise VideoProcessingError("결과 동영상 파일이 정상적으로 생성되지 않았습니다.")

    return {
        "input_metadata": metadata.to_dict(),
        "processed_frames": processed_frames,
        "output_path": str(output_path),
        "output_size_bytes": output_path.stat().st_size,
    }
    
    
    
def find_positive_segments(
    frame_results: list[dict[str, object]],
    threshold: float,
    fps: float,
) -> list[dict[str, object]]:
    """
    협착 확률이 임계값 이상인 연속 프레임 구간을 찾는다.

    한 프레임만 임계값 이상이어도 하나의 후보 구간으로 기록하지만,
    최종 화면에서는 구간 길이를 함께 제공하여 단일 프레임 오탐과
    연속적으로 유지되는 후보를 구분할 수 있도록 한다.
    """
    segments: list[dict[str, object]] = []
    segment_start: int | None = None

    for result in frame_results:
        frame_index = int(result["frame_index"])
        stenosis_probability = float(
            result["probabilities"]["stenosis"]
        )

        is_positive = stenosis_probability >= threshold

        if is_positive and segment_start is None:
            segment_start = frame_index

        if not is_positive and segment_start is not None:
            segment_end = frame_index - 1

            segments.append(
                {
                    "start_frame": segment_start,
                    "end_frame": segment_end,
                    "frame_count": (segment_end - segment_start + 1),
                    "start_time_seconds": (segment_start / fps),
                    "end_time_seconds": ( segment_end / fps),
                }
            )

            segment_start = None

    if segment_start is not None:
        segment_end = int(frame_results[-1]["frame_index"])

        segments.append(
            {"start_frame": segment_start,
              "end_frame": segment_end,
              "frame_count": (segment_end - segment_start + 1),
              "start_time_seconds": segment_start / fps,
              "end_time_seconds": segment_end / fps,
            }
        )

    return segments


def build_video_summary(
    frame_results: list[dict[str, object]],
    fps: float,
    threshold: float = 0.5,
    top_k: int = 5,
) -> dict[str, object]:
    """
    프레임별 협착 확률로 영상 전체 참고 요약을 생성한다.

    이 함수는 영상을 Normal 또는 Stenosis로 확정하지 않으며,
    의료진 검토에 필요한 후보 프레임과 통계만 제공한다.
    """
    if not frame_results:
        raise VideoProcessingError("영상 요약을 생성할 프레임 결과가 없습니다.")

    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold는 0과 1 사이여야 합니다.")

    if top_k <= 0:
        raise ValueError("top_k는 1 이상이어야 합니다.")

    sorted_results = sorted(
        frame_results,
        key=lambda result: float(
            result["probabilities"]["stenosis"]
        ),
        reverse=True,
    )

    highest_result = sorted_results[0]

    actual_top_k = min(top_k, len(sorted_results),)

    top_results = sorted_results[:actual_top_k]

    top_k_mean = sum(
        float(result["probabilities"]["stenosis"])
        for result in top_results
    ) / actual_top_k
    
    average_stenosis_probability = sum(
        
        float(result["probabilities"]["stenosis"])
        for result in frame_results
    ) / len(frame_results)
    

    frames_above_threshold = [
        result
        for result in frame_results
        if float(
            result["probabilities"]["stenosis"]
        ) >= threshold
    ]

    positive_segments = find_positive_segments(
        frame_results=frame_results,
        threshold=threshold,
        fps=fps,
    )

    longest_consecutive_positive_frames = max(
        (
            int(segment["frame_count"])
            for segment in positive_segments
        ),
        default=0,
    )

    return {
        "frame_count": len(frame_results),
        "threshold": threshold,
        "highest_stenosis_probability": float(
            highest_result["probabilities"]["stenosis"]
        ),
        
        "average_stenosis_probability": (average_stenosis_probability),
        
        "highest_probability_frame_index": int(highest_result["frame_index"]),
        "highest_probability_timestamp_seconds": float(highest_result["timestamp_seconds"]),
        "frames_above_threshold": len(frames_above_threshold),
        "frames_above_threshold_ratio": (len(frames_above_threshold)/ len(frame_results)),
        "top_k": actual_top_k,
        "top_k_stenosis_probability_mean": (top_k_mean),
        "longest_consecutive_positive_frames": (longest_consecutive_positive_frames),
        "positive_segments": positive_segments, 
    }

def draw_frame_information(
    frame: np.ndarray,
    frame_index: int,
    total_frames: int,
    timestamp_seconds: float,
    predicted_label: str,
    stenosis_probability: float,
) -> np.ndarray:
    """
    글씨 너비를 계산하여 프레임 밖으로 벗어나지 않도록 자동 조절한다.
    배경과 외곽선 없이 흰색 글씨만 표시한다.
    """
    output_frame = frame.copy()

    lines = [
        f"Frame {frame_index + 1}/{total_frames}",
        f"Time {timestamp_seconds:.2f}s",
        f"Stenosis {stenosis_probability * 100:.1f}%",
        f"Prediction {predicted_label}",
    ]

    font = cv2.FONT_HERSHEY_SIMPLEX
    base_font_scale = 0.5
    text_thickness = 2

    margin_x = 24
    margin_y = 12
    available_width = frame.shape[1] - margin_x * 2

    adjusted_scales = []

    for line in lines:
        font_scale = base_font_scale

        while font_scale > 0.30:
            text_size, _ = cv2.getTextSize(
                line,
                font,
                font_scale,
                text_thickness,
            )

            text_width = text_size[0]

            if text_width <= available_width:
                break

            font_scale -= 0.02

        adjusted_scales.append(font_scale)

    line_height = 25
    start_y = margin_y + 20

    for line_index, line in enumerate(lines):
        font_scale = adjusted_scales[line_index]
        text_y = start_y + line_index * line_height

        cv2.putText(
            output_frame,
            line,
            (margin_x, text_y),
            font,
            font_scale,
            (255, 255, 255),
            text_thickness,
            cv2.LINE_AA,
        )

    return output_frame


def classify_video_frames(
    input_path: Path,
    output_path: Path | None = None,
    render_output_video: bool = False,
    save_gradcam_images: bool = False,
) -> dict[str, object]:
    """
    입력 동영상의 모든 프레임에 InceptionV3 분류를 수행한다.

    프레임별 분류 결과와 영상 전체 참고 요약을 반환하며,
    render_output_video가 True인 경우 Grad-CAM과 프레임 정보를
    합성한 결과 MP4를 생성한다.

    save_gradcam_images가 True인 경우 Stenosis로 예측된 프레임의
    투명 Grad-CAM 이미지를 별도 PNG 파일로 저장한다.
    """
    metadata = read_video_metadata(input_path)

    capture = cv2.VideoCapture(str(input_path))

    if not capture.isOpened():
        raise VideoProcessingError("분류 처리를 위해 동영상을 열 수 없습니다.")

    writer: cv2.VideoWriter | None = None

    if render_output_video:
        if output_path is None:
            capture.release()

            raise ValueError("render_output_video가 True이면 output_path가 필요합니다.")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        writer = cv2.VideoWriter(
            str(output_path),
            fourcc,
            metadata.fps,
            (metadata.width, metadata.height),
        )

        if not writer.isOpened():
            capture.release()

            raise VideoProcessingError("분류 결과 MP4 파일을 생성할 수 없습니다.")

    analysis_id: str | None = None
    gradcam_directory: Path | None = None

    if save_gradcam_images:
        (
            analysis_id,
            gradcam_directory,
        ) = create_gradcam_analysis_directory()

    frame_results: list[dict[str, object]] = []

    processed_frames = 0
    stenosis_frame_count = 0
    normal_frame_count = 0

    try:
        while True:
            success, frame = capture.read()

            if not success:
                break

            if frame is None:
                raise VideoProcessingError(f"{processed_frames}번째 이후 프레임을 읽지 못했습니다.")

            frame_height, frame_width = frame.shape[:2]

            if (
                frame_width != metadata.width
                or frame_height != metadata.height
            ):
                frame = cv2.resize(frame,
                    (metadata.width, metadata.height),
                    interpolation=cv2.INTER_AREA,
                )

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB,)
            pil_image = Image.fromarray(rgb_frame)
            gradcam_result = generate_gradcam_data(image=pil_image,
                                                    target_class=1,
                                                    alpha=0.45,)

            probabilities = gradcam_result["probabilities"]

            if not isinstance(probabilities, dict):
                raise VideoProcessingError("Grad-CAM 확률 정보 형식이 올바르지 않습니다.")

            normal_probability = float(probabilities["normal"])
            stenosis_probability = float(probabilities["stenosis"])
            timestamp_seconds = (processed_frames / metadata.fps)
            predicted_class = int(gradcam_result["predicted_class"])
            predicted_label = str(gradcam_result["predicted_label"])
            show_gradcam = bool(gradcam_result["show_gradcam"])
            gradcam_relative_path: str | None = None

            if (
                save_gradcam_images
                and show_gradcam
                and gradcam_directory is not None
                and analysis_id is not None
            ):
                transparent_heatmap_image = (gradcam_result.get("transparent_heatmap_image"))

                if transparent_heatmap_image is not None:
                    heatmap_filename = (f"frame_{processed_frames:06d}.png")
                    heatmap_path = (gradcam_directory / heatmap_filename)
                    transparent_heatmap_image.save(heatmap_path, format="PNG",)
                    gradcam_relative_path = (
                        f"{analysis_id}/"
                        f"{heatmap_filename}"
                    )

            frame_result = {
                "frame_index": processed_frames,
                "frame_number": processed_frames + 1,
                "timestamp_seconds": timestamp_seconds,
                "predicted_class": predicted_class,
                "predicted_label": predicted_label,
                "confidence": float(gradcam_result["confidence"]),
                "show_gradcam": show_gradcam,
                "gradcam_relative_path": (gradcam_relative_path),
                "gradcam_url": None,
                "probabilities": {"normal": normal_probability,"stenosis": stenosis_probability,},
            }

            frame_results.append(frame_result)

            if predicted_label == "Stenosis":
                stenosis_frame_count += 1
            else:
                normal_frame_count += 1

            if render_output_video:
                overlay_image = gradcam_result["overlay_image"]

                if overlay_image is not None:
                    overlay_rgb = np.asarray(
                        overlay_image.convert("RGB"),
                        dtype=np.uint8,)

                    display_frame = cv2.cvtColor(
                        overlay_rgb,
                        cv2.COLOR_RGB2BGR,)

                    display_frame = cv2.resize(
                        display_frame,
                        (metadata.width, metadata.height),
                        interpolation=cv2.INTER_LINEAR,
                    )
                else:
                    display_frame = frame.copy()

                visualized_frame = draw_frame_information(
                    frame=display_frame,
                    frame_index=processed_frames,
                    total_frames=metadata.frame_count,
                    timestamp_seconds=timestamp_seconds,
                    predicted_label=predicted_label,
                    stenosis_probability=(stenosis_probability),
                )

                if writer is None:
                    raise VideoProcessingError("결과 영상 writer가 초기화되지 않았습니다.")

                writer.write(visualized_frame)

            processed_frames += 1

    finally:
        capture.release()

        if writer is not None:
            writer.release()

    if processed_frames == 0:
        if output_path is not None:
            output_path.unlink(missing_ok=True)

        if (gradcam_directory is not None
            and gradcam_directory.exists()
        ):
            gradcam_directory.rmdir()

        raise VideoProcessingError("분류 처리된 프레임이 없습니다.")

    if render_output_video:
        if output_path is None:
            raise VideoProcessingError("결과 영상 경로가 설정되지 않았습니다.")

        if (not output_path.exists()
            or output_path.stat().st_size == 0
        ):
            output_path.unlink(missing_ok=True)

            raise VideoProcessingError("분류 결과 동영상이 정상적으로 생성되지 않았습니다.")

    normal_frame_ratio = (normal_frame_count / processed_frames)
    stenosis_frame_ratio = (stenosis_frame_count / processed_frames)
    video_summary = build_video_summary(
        frame_results=frame_results,
        fps=metadata.fps,
        threshold=0.5,
        top_k=5,
    )

    result: dict[str, object] = {
        "analysis_id": analysis_id,
        "input_metadata": metadata.to_dict(),
        "processed_frames": processed_frames,
        "rendered_output_video": (render_output_video),
        "video_summary": video_summary,
        "frame_summary": {"normal_frame_count": (normal_frame_count),
            "stenosis_frame_count": (stenosis_frame_count),
            "normal_frame_ratio": (normal_frame_ratio),
            "stenosis_frame_ratio": (stenosis_frame_ratio),},
        "frames": frame_results,
    }

    if (render_output_video
        and output_path is not None
    ):
        result["output_path"] = str(output_path)
        result["output_size_bytes"] = (output_path.stat().st_size)
    else:
        result["output_path"] = None
        result["output_size_bytes"] = None

    return result

def build_detection_summary(
    frame_results: list[dict[str, object]],
) -> dict[str, object]:
    """
    프레임별 YOLO 탐지 결과를 기반으로 영상 전체 참고 요약을 생성한다.

    이 요약은 병변을 확정하지 않고 탐지된 프레임 수,
    전체 Bounding Box 수와 최고 confidence 위치를 반환한다.
    """
    if not frame_results:
        raise VideoProcessingError("YOLO 영상 요약을 생성할 프레임 결과가 없습니다.")

    detected_frames = [
        frame_result
        for frame_result in frame_results
        if int(frame_result["detection_count"]) > 0
    ]

    all_detections = [
        {
            "frame_index": int(frame_result["frame_index"]),
            "frame_number": int(frame_result["frame_number"]),
            "timestamp_seconds": float(frame_result["timestamp_seconds"]),
            **detection,
        }
        for frame_result in frame_results
        for detection in frame_result["detections"]
    ]

    highest_confidence_detection = None

    if all_detections:
        highest_confidence_detection = max(
            all_detections,
            key=lambda detection: float(
                detection["confidence"]
            ),
        )

    return {
        "frame_count": len(frame_results),
        "detected_frame_count": len(detected_frames),
        "detected_frame_ratio": (len(detected_frames) / len(frame_results)),
        "total_detection_count": len(all_detections),
        "highest_confidence_detection": (highest_confidence_detection),
    }
    
def detect_video_frames(
    input_path: Path,
    confidence_threshold: float = YOLO_CONFIDENCE_THRESHOLD,
    iou_threshold: float = YOLO_IOU_THRESHOLD,
) -> dict[str, object]:
    """
    입력 동영상의 모든 프레임에 YOLO 객체 탐지를 수행한다.

    이 함수는 결과 MP4를 생성하지 않고 프레임별 Bounding Box,
    confidence, 클래스와 영상 전체 참고 요약을 반환한다.
    """
    if not input_path.exists():
        raise VideoProcessingError(f"입력 동영상 파일을 찾을 수 없습니다: {input_path}")

    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold는 0 이상 1 이하이어야 합니다.")

    if not 0.0 <= iou_threshold <= 1.0:
        raise ValueError("iou_threshold는 0 이상 1 이하이어야 합니다.")
        
    # 동영상 메타데이터 확인부터 두 모델의 전체 분석이 끝날 때까지
    # 소요되는 시간을 측정하기 위해 고해상도 타이머를 시작한다.
    analysis_started_at = perf_counter()
        

    # FPS,해상도와 전체 프레임 수는 timestamp 계산과 
    # React의 프레임 동기화에 사용하므로 분석 전에 검증
    metadata = read_video_metadata(input_path)

    capture = cv2.VideoCapture(str(input_path))

    if not capture.isOpened():
        raise VideoProcessingError(
            "YOLO 탐지를 위해 동영상을 열 수 없습니다."
        )

    frame_results: list[dict[str, object]] = []
    processed_frames = 0

    try:
        while True:
            success, frame = capture.read()

            if not success:
                break

            if frame is None:
                raise VideoProcessingError(f"{processed_frames}번째 프레임을 읽지 못했습니다.")

            frame_height, frame_width = frame.shape[:2]

            if (frame_width != metadata.width
                or frame_height != metadata.height
            ):
                frame = cv2.resize(
                    frame,
                    (metadata.width, metadata.height),
                    interpolation=cv2.INTER_AREA,
                )

            timestamp_seconds = (
                processed_frames / metadata.fps
            )

            detection_result = detect_image(
                image=frame,
                confidence_threshold=confidence_threshold,
                iou_threshold=iou_threshold,
            )
            
            detections = detection_result["detections"]
            for detection_index, detection in enumerate(detections):
                detection["detection_id"] = (
                    f"frame_{processed_frames}_det_{detection_index}"
                )
                
            annotations = map_yolo_detections_to_annotations(
                detections,
                media_type="video",
                frame_index=processed_frames,
            )
                
            

            frame_results.append(
                {
                    "frame_index": processed_frames,
                    "frame_number": processed_frames + 1,
                    "timestamp_seconds": round(timestamp_seconds, 6,),
                    "image_width": int(detection_result["image_width"]),
                    "image_height": int(detection_result["image_height"]),
                    "detection_count": int(detection_result["detection_count"]),
                    "detections": detections,
                    "annotations": annotations,
                }
            )

            processed_frames += 1

    finally:
        capture.release()

    if processed_frames == 0:
        raise VideoProcessingError(
            "YOLO 탐지가 수행된 프레임이 없습니다."
        )

    detection_summary = build_detection_summary(
        frame_results
    )

    return {
        "input_metadata": metadata.to_dict(),
        "processed_frames": processed_frames,
        "confidence_threshold": confidence_threshold,
        "iou_threshold": iou_threshold,
        "frame_results": frame_results,
        "detection_summary": detection_summary,
        "rendered_output_video": False,
        "output_path": None,
    }   


def analyze_video_frames(
    input_path: Path,
    confidence_threshold: float = YOLO_CONFIDENCE_THRESHOLD,
    iou_threshold: float = YOLO_IOU_THRESHOLD,
    save_gradcam_images: bool = True,
) -> dict[str, object]:
    """
    입력 동영상을 한 번만 순회하면서 InceptionV3 분류·Grad-CAM과
    YOLO 탐지를 함께 수행한다.

    목적:
        기존 분류 API와 탐지 API를 따로 호출하면 같은 영상을 두 번
        디코딩해야 하므로, 통합 분석에서는 프레임을 한 번만 읽고
        동일한 frame_index를 기준으로 두 모델의 결과를 결합한다.

    Args:
        input_path:
            분석할 동영상의 로컬 임시 저장 경로.
        confidence_threshold:
            YOLO 탐지 결과에 포함할 최소 confidence.
        iou_threshold:
            YOLO NMS에 사용할 IoU 임계값.
        save_gradcam_images:
            React 오버레이용 투명 Grad-CAM PNG 저장 여부.

    Returns:
        공통 analysis_id, 동영상 메타데이터, 분류 요약,
        탐지 요약과 프레임별 통합 결과를 반환한다.
    """
    # 라우터에서 전달된 임시 파일이 실제로 존재하는지 먼저 확인한다.
    # 존재하지 않는 경로를 OpenCV에 전달하면 원인을 파악하기 어려운
    # 동영상 열기 오류가 발생하므로 서비스 진입 시 명확히 차단한다.
    if not input_path.exists():
        raise VideoProcessingError(
            f"입력 동영상 파일을 찾을 수 없습니다: {input_path}"
        )

    # YOLO 서비스와 동일한 유효 범위를 적용하여
    # 잘못된 임계값이 모델 호출 단계까지 전달되지 않도록 한다.
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError(
            "confidence_threshold는 0 이상 1 이하이어야 합니다."
        )

    if not 0.0 <= iou_threshold <= 1.0:
        raise ValueError(
            "iou_threshold는 0 이상 1 이하이어야 합니다."
        )
    # 통합 분석 전체 처리 시간을 측정하기 위한 시작시각
    analysis_started_at = perf_counter()

    # FPS, 해상도와 전체 프레임 수는 timestamp 계산과
    # React의 프레임 동기화에 사용하므로 분석 전에 검증한다.
    metadata = read_video_metadata(input_path)

    capture = cv2.VideoCapture(str(input_path))

    if not capture.isOpened():
        raise VideoProcessingError(
            "통합 AI 분석을 위해 동영상을 열 수 없습니다."
        )

    # 분류 결과, YOLO 결과와 Grad-CAM 이미지를 하나의 분석 단위로
    # 묶기 위해 요청마다 공통 analysis_id를 한 번만 생성한다.
    analysis_id = uuid4().hex

    gradcam_directory: Path | None = None

    if save_gradcam_images:
        # 기존 create_gradcam_analysis_directory()를 사용하면 별도의
        # analysis_id가 다시 생성되므로, 통합 분석에서는 위에서 만든
        # 공통 analysis_id를 그대로 디렉터리 이름으로 사용한다.
        gradcam_directory = (
            GRADCAM_OUTPUT_DIR / analysis_id
        )

        gradcam_directory.mkdir(
            parents=True,
            exist_ok=False,
        )

    # React에 반환할 최종 통합 프레임 배열이다.
    integrated_frames: list[dict[str, object]] = []

    # 기존 요약 함수를 재사용하기 위해 분류용 프레임 배열과
    # 탐지용 프레임 배열도 별도로 구성한다.
    classification_frames: list[dict[str, object]] = []
    detection_frames: list[dict[str, object]] = []

    processed_frames = 0
    normal_frame_count = 0
    stenosis_frame_count = 0

    try:
        while True:
            success, frame = capture.read()

            # OpenCV에서 success=False는 정상적인 영상 종료도 의미하므로
            # 더 읽을 프레임이 없으면 반복을 종료한다.
            if not success:
                break

            if frame is None:
                raise VideoProcessingError(
                    f"{processed_frames}번째 프레임을 "
                    "정상적으로 읽지 못했습니다."
                )

            frame_height, frame_width = frame.shape[:2]

            # 일부 영상은 메타데이터 해상도와 실제 프레임 해상도가
            # 다를 수 있으므로 모든 모델에 동일한 크기의 프레임을 전달한다.
            if (
                frame_width != metadata.width
                or frame_height != metadata.height
            ):
                frame = cv2.resize(
                    frame,
                    (metadata.width, metadata.height),
                    interpolation=cv2.INTER_AREA,
                )

            # 프레임 번호를 원본 FPS로 나누어 현재 재생 시간을 계산한다.
            # React는 이 값을 video.currentTime과 비교해 오버레이를 선택한다.
            timestamp_seconds = (
                processed_frames / metadata.fps
            )

            # ---------------------------------------------------------
            # 1. InceptionV3 분류와 Grad-CAM 생성
            # ---------------------------------------------------------

            # OpenCV 프레임은 BGR이고 InceptionV3 전처리는 RGB PIL 이미지를
            # 사용하므로 색상 순서를 변환한 후 PIL 이미지로 만든다.
            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )

            pil_image = Image.fromarray(rgb_frame)

            # generate_gradcam_data()는 한 번의 forward 결과로
            # 분류 확률과 Grad-CAM을 함께 생성하므로 predict()를 별도로
            # 호출하지 않아 프레임당 중복 Inception 추론을 방지한다.
            gradcam_result = generate_gradcam_data(
                image=pil_image,
                target_class=1,
                alpha=0.45,
            )

            probabilities = gradcam_result.get(
                "probabilities"
            )

            if not isinstance(probabilities, dict):
                raise VideoProcessingError("InceptionV3 확률 결과 형식이 올바르지 않습니다."
                )

            normal_probability = float(probabilities["normal"])
            stenosis_probability = float(probabilities["stenosis"])
            predicted_class = int(gradcam_result["predicted_class"])
            predicted_label = str(gradcam_result["predicted_label"])
            show_gradcam = bool(gradcam_result["show_gradcam"])
            gradcam_relative_path: str | None = None

            # Stenosis로 판단되어 show_gradcam=True인 프레임만
            # 투명 PNG로 저장하여 불필요한 파일 생성을 줄인다.
            if (
                save_gradcam_images
                and show_gradcam
                and gradcam_directory is not None
            ):
                transparent_heatmap_image = (
                    gradcam_result.get("transparent_heatmap_image")
                )

                if transparent_heatmap_image is not None:
                    heatmap_filename = (f"frame_{processed_frames:06d}.png")

                    heatmap_path = (gradcam_directory / heatmap_filename)

                    transparent_heatmap_image.save(heatmap_path, format="PNG",)

                    # 라우터가 request.url_for()를 이용해 공개 URL로
                    # 변환할 수 있도록 정적 폴더 기준 상대 경로만 저장한다.
                    gradcam_relative_path = (
                        f"{analysis_id}/"
                        f"{heatmap_filename}"
                    )

            classification_result = {
                "frame_index": processed_frames,
                "frame_number": processed_frames + 1,
                "timestamp_seconds": round(
                    timestamp_seconds,
                    6,
                ),
                "predicted_class": predicted_class,
                "predicted_label": predicted_label,
                "confidence": float(
                    gradcam_result["confidence"]
                ),
                "show_gradcam": show_gradcam,
                "gradcam_relative_path": (
                    gradcam_relative_path
                ),
                # 실제 공개 URL은 Request 객체가 있는 라우터에서 생성한다.
                "gradcam_url": None,
                "probabilities": {
                    "normal": normal_probability,
                    "stenosis": stenosis_probability,
                },
            }

            classification_frames.append(
                classification_result
            )

            if predicted_label == "Stenosis":
                stenosis_frame_count += 1
            else:
                normal_frame_count += 1

            # ---------------------------------------------------------
            # 2. 동일 프레임에서 YOLO 탐지 수행
            # ---------------------------------------------------------

            # detect_image()에 같은 OpenCV 프레임을 전달하여
            # 동영상을 다시 디코딩하지 않고 YOLO 탐지를 수행한다.
            detection_result = detect_image(
                image=frame,
                confidence_threshold=(
                    confidence_threshold
                ),
                iou_threshold=iou_threshold,
            )

            detections = detection_result["detections"]

            if not isinstance(detections, list):
                raise VideoProcessingError(
                    "YOLO detections 결과 형식이 "
                    "올바르지 않습니다."
                )

            # 이미지 탐지에서 생성된 det_0 형식의 ID를
            # 동영상 전체에서 중복되지 않는 frame_n_det_n 형식으로 바꾼다.
            for detection_index, detection in enumerate(
                detections
            ):
                detection["detection_id"] = (
                    f"frame_{processed_frames}"
                    f"_det_{detection_index}"
                )

            # React에서 Bounding Box를 이동하거나 크기를 수정할 수 있도록
            # 기존 YOLO 결과를 편집 가능한 Annotation 규격으로 변환한다.
            annotations = (
                map_yolo_detections_to_annotations(
                    detections,
                    media_type="video",
                    frame_index=processed_frames,
                )
            )

            detection_frame_result = {
                "frame_index": processed_frames,
                "frame_number": processed_frames + 1,
                "timestamp_seconds": round(
                    timestamp_seconds,
                    6,
                ),
                "image_width": int(
                    detection_result["image_width"]
                ),
                "image_height": int(
                    detection_result["image_height"]
                ),
                "detection_count": int(
                    detection_result["detection_count"]
                ),
                "detections": detections,
                "annotations": annotations,
            }

            detection_frames.append(
                detection_frame_result
            )

            # ---------------------------------------------------------
            # 3. 같은 frame_index의 두 모델 결과를 하나로 결합
            # ---------------------------------------------------------

            # 분류·Grad-CAM과 YOLO 결과를 중첩 구조로 분리해 두면
            # React가 각 시각화 기능을 독립적으로 켜고 끌 수 있다.
            integrated_frames.append(
                {
                    "frame_index": processed_frames,
                    "frame_number": (processed_frames + 1),
                    "timestamp_seconds": round(timestamp_seconds, 6,),
                    "classification": {"predicted_class": (predicted_class),
                        "predicted_label": (predicted_label),
                        "confidence": float(gradcam_result["confidence"]),
                        "probabilities": {"normal": (normal_probability),
                            "stenosis": (stenosis_probability),},},
                    "gradcam": {"available": bool(gradcam_relative_path),
                        "show_gradcam": (show_gradcam),
                        "relative_path": (gradcam_relative_path),
                        # 라우터에서 정적 파일 URL로 변환한다.
                        "url": None,},
                    "detection_count": int(
                        detection_result["detection_count"]),
                    "detections": detections,
                    "annotations": annotations,
                }
            )

            processed_frames += 1

    finally:
        # 정상 처리와 예외 발생 모두에서 파일 핸들을 반환해야
        # Windows에서 임시 업로드 파일을 삭제할 수 있다.
        capture.release()

    if processed_frames == 0:
        raise VideoProcessingError(
            "통합 AI 분석이 수행된 프레임이 없습니다."
        )

    # 프레임 처리 수와 각 결과 배열 길이가 다르면
    # React에서 같은 frame_index를 기준으로 결합할 수 없으므로 실패시킨다.
    if not (
        len(integrated_frames)
        == len(classification_frames)
        == len(detection_frames)
        == processed_frames
    ):
        raise VideoProcessingError(
            "통합 분석의 프레임 결과 개수가 "
            "서로 일치하지 않습니다."
        )
        
    # 각 통합 프레임의 인덱스와 내부 결과가 서로 일치하는지 검증한다.
    #
    # 배열 길이만 같아도 frame_index가 중복되거나 누락될 수 있으므로,
    # React가 video.currentTime과 AI 결과를 안전하게 연결할 수 있도록
    # 프레임별 내부 상태까지 검사한다.
    for expected_index, frame_result in enumerate(
        integrated_frames
    ):
        # frame_index는 0부터 처리 순서대로 연속되어야 한다.
        if frame_result["frame_index"] != expected_index:
            raise VideoProcessingError(
                f"{expected_index}번째 통합 결과의 "
                "frame_index가 올바르지 않습니다."
            )

        detections = frame_result["detections"]
        annotations = frame_result["annotations"]

        # 탐지 결과마다 편집 가능한 Annotation이 하나씩 생성되어야
        # React에서 원본 박스와 편집 박스를 정확히 연결할 수 있다.
        if len(detections) != len(annotations):
            raise VideoProcessingError(
                f"{expected_index}번째 프레임의 "
                "탐지 결과와 Annotation 개수가 "
                "일치하지 않습니다."
            )

        detection_count = int(
            frame_result["detection_count"]
        )

        # detection_count와 실제 detections 배열 길이가 다르면
        # 프론트 요약 수치와 화면에 그려지는 박스 수가 달라질 수 있다.
        if detection_count != len(detections):
            raise VideoProcessingError(
                f"{expected_index}번째 프레임의 "
                "detection_count와 detections 개수가 "
                "일치하지 않습니다."
            )

        gradcam_result = frame_result["gradcam"]

        if not isinstance(gradcam_result, dict):
            raise VideoProcessingError(
                f"{expected_index}번째 프레임의 "
                "Grad-CAM 결과 형식이 올바르지 않습니다."
            )

        relative_path = gradcam_result.get(
            "relative_path"
        )

        available = bool(
            gradcam_result.get("available")
        )

        # Grad-CAM 파일 상대 경로가 있을 때만 available이 True여야 한다.
        # 두 값이 다르면 React에서 존재하지 않는 이미지를 요청할 수 있다.
        if bool(relative_path) != available:
            raise VideoProcessingError(
                f"{expected_index}번째 프레임의 "
                "Grad-CAM 사용 가능 상태와 "
                "파일 경로가 일치하지 않습니다."
            )   


    # 기존 분류 요약 함수를 재사용하여 최고 협착 확률,
    # 양성 후보 구간과 연속 프레임 정보를 생성한다.
    classification_summary = build_video_summary(
        frame_results=classification_frames,
        fps=metadata.fps,
        threshold=0.5,
        top_k=5,
    )

    # 기존 YOLO 요약 함수를 재사용하여 탐지 프레임 비율,
    # 전체 박스 수와 최고 confidence 탐지를 생성한다.
    detection_summary = build_detection_summary(frame_results=detection_frames,)
    normal_frame_ratio = (normal_frame_count / processed_frames)
    stenosis_frame_ratio = (stenosis_frame_count / processed_frames)
    
    # 메타데이터 확인, 프레임 디코딩, InceptionV3·Grad-CAM,
    # YOLO 탐지와 결과 결합까지 포함한 전체 처리 시간을 계산한다.
    total_processing_seconds = (perf_counter() - analysis_started_at)

    # 전체 처리 시간을 실제 처리 프레임 수로 나누어
    # 한 프레임을 분석하는 데 걸린 평균 시간을 계산한다.
    average_seconds_per_frame = (total_processing_seconds / processed_frames)

    # 서버가 실제 시간 1초 동안 처리한 평균 프레임 수를 계산한다.
    # 이 값은 원본 영상 FPS가 아니라 AI 추론 처리 성능이다.
    processing_fps = (
        processed_frames / total_processing_seconds
        if total_processing_seconds > 0
        else 0.0
    )
    
    

    return {
        "analysis_id": analysis_id,
        "input_metadata": metadata.to_dict(),
        "processed_frames": processed_frames,
        "performance": {
            # 전체 통합 분석 처리 시간이다.
            "total_processing_seconds": round(total_processing_seconds, 4,),

            # 한 프레임당 평균 처리 시간이다.
            "average_seconds_per_frame": round(average_seconds_per_frame,6,),

            # 현재 서버 환경에서 초당 처리한 평균 프레임 수이다.
            "processing_fps": round(processing_fps,4,),

            # 원본 영상 FPS와 AI 처리 FPS를 비교할 수 있도록 제공한다.
            "source_video_fps": round(metadata.fps,4,),

            # 처리 FPS가 원본 FPS 이상인지 여부를 반환한다.
            # true라고 해서 네트워크와 React 렌더링까지 포함한
            # 전체 서비스가 실시간이라는 의미는 아니다.
            "faster_than_source_playback": (
                processing_fps >= metadata.fps
            ),
        },
        "rendered_output_video": False,
        "output_path": None,
        "classification_summary": (classification_summary),
        "classification_frame_summary": {
            "normal_frame_count": (normal_frame_count),
            "stenosis_frame_count": (stenosis_frame_count),
            "normal_frame_ratio": (normal_frame_ratio),
            "stenosis_frame_ratio": (stenosis_frame_ratio),
        },
        "detection_summary": detection_summary,
        "confidence_threshold": (confidence_threshold),
        "iou_threshold": iou_threshold,
        "frames": integrated_frames,
    }
