# HTTP 자동 테스트 -> 천체 app.py를 불러오면 모델까지 로딩 될 수 있으므로 annotation 라우터만 붙인 작은 테스트 앱 사용
from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.annotation import router as annotation_router


test_app = FastAPI()
test_app.include_router(annotation_router)

client = TestClient(test_app)


def make_image_request() -> dict:
    return {
        "exam_id": 101,
        "analysis_id": "analysis_image_001",
        "patient_id": "P001",
        "media_type": "image",
        "annotation_context": {
            "mode": "image",
        },
        "coordinate_system": {
            "type": "normalized",
            "range": [0.0, 1.0],
            "origin": "top_left",
        },
        "annotations": [
            {
                "annotation_type": "bounding_box",
                "annotation_id": "image_det_0",
                "detection_id": "det_0",
                "source": "ai",
                "edit_status": "original",
                "class_id": 0,
                "class_name": "Lesion",
                "ai_confidence": 0.81,
                "original_box_normalized": {
                    "x1": 0.2,
                    "y1": 0.3,
                    "x2": 0.5,
                    "y2": 0.6,
                },
                "edited_box_normalized": None,
            }
        ],
        "is_finalized": False,
    }


def make_video_request() -> dict:
    return {
        "exam_id": 101,
        "analysis_id": "analysis_video_001",
        "patient_id": "P001",
        "media_type": "video",
        "annotation_context": {
            "mode": "paused_frame",
            "frame_index": 40,
            "timestamp_seconds": 3.2,
            "bookmark_id": None,
        },
        "coordinate_system": {
            "type": "normalized",
            "range": [0.0, 1.0],
            "origin": "top_left",
        },
        "annotations": [
            {
                "annotation_type": "bounding_box",
                "annotation_id": "frame_40_det_0",
                "detection_id": "frame_40_det_0",
                "source": "ai",
                "edit_status": "modified",
                "class_id": 0,
                "class_name": "Lesion",
                "ai_confidence": 0.603294,
                "original_box_normalized": {
                    "x1": 0.627126,
                    "y1": 0.590411,
                    "x2": 0.770497,
                    "y2": 0.72374,
                },
                "edited_box_normalized": {
                    "x1": 0.61,
                    "y1": 0.58,
                    "x2": 0.79,
                    "y2": 0.75,
                },
            }
        ],
        "is_finalized": False,
    }


def test_valid_image_request() -> None:
    response = client.post(
        "/annotations/validate",
        json=make_image_request(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["media_type"] == "image"
    assert (
        body["data"]["annotations"][0]["annotation_id"]
        == "image_det_0"
    )


def test_valid_video_request() -> None:
    response = client.post(
        "/annotations/validate",
        json=make_video_request(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert (
        body["data"]["annotation_context"]["frame_index"]
        == 40
    )


def test_image_rejects_frame_index() -> None:
    request_data = make_image_request()

    request_data["annotation_context"]["frame_index"] = 0

    response = client.post(
        "/annotations/validate",
        json=request_data,
    )

    assert response.status_code == 422


def test_video_requires_frame_index() -> None:
    request_data = make_video_request()

    request_data["annotation_context"]["frame_index"] = None

    response = client.post(
        "/annotations/validate",
        json=request_data,
    )

    assert response.status_code == 422


def test_invalid_coordinate_range() -> None:
    request_data = make_image_request()

    request_data["annotations"][0][
        "original_box_normalized"
    ]["x2"] = 1.2

    response = client.post(
        "/annotations/validate",
        json=request_data,
    )

    assert response.status_code == 422


def test_invalid_box_order() -> None:
    request_data = make_image_request()

    request_data["annotations"][0][
        "original_box_normalized"
    ] = {
        "x1": 0.5,
        "y1": 0.3,
        "x2": 0.2,
        "y2": 0.6,
    }

    response = client.post(
        "/annotations/validate",
        json=request_data,
    )

    assert response.status_code == 422


def test_modified_requires_edited_box() -> None:
    request_data = make_image_request()

    annotation = request_data["annotations"][0]
    annotation["edit_status"] = "modified"
    annotation["edited_box_normalized"] = None

    response = client.post(
        "/annotations/validate",
        json=request_data,
    )

    assert response.status_code == 422


def test_duplicate_annotation_id() -> None:
    request_data = make_image_request()

    duplicated = deepcopy(
        request_data["annotations"][0]
    )

    duplicated["detection_id"] = "det_1"

    request_data["annotations"].append(duplicated)

    response = client.post(
        "/annotations/validate",
        json=request_data,
    )

    assert response.status_code == 422


def test_validation_api_does_not_report_saved() -> None:
    response = client.post(
        "/annotations/validate",
        json=make_image_request(),
    )

    assert response.status_code == 200

    body = response.json()

    assert "saved" not in body
    assert "created" not in body
    assert "database_id" not in body


def main() -> None:
    test_valid_image_request()
    print("정상 이미지 HTTP 테스트 성공")

    test_valid_video_request()
    print("정상 동영상 HTTP 테스트 성공")

    test_image_rejects_frame_index()
    print("이미지 frame_index 거부 테스트 성공")

    test_video_requires_frame_index()
    print("동영상 frame_index 필수 테스트 성공")

    test_invalid_coordinate_range()
    print("좌표 범위 검증 테스트 성공")

    test_invalid_box_order()
    print("Bounding Box 순서 검증 테스트 성공")

    test_modified_requires_edited_box()
    print("수정 Box 필수 검증 테스트 성공")

    test_duplicate_annotation_id()
    print("중복 Annotation ID 검증 테스트 성공")

    test_validation_api_does_not_report_saved()
    print("비저장 검증 API 테스트 성공")

    print("모든 Annotation HTTP 테스트 성공")


if __name__ == "__main__":
    main()