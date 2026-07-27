from fastapi import FastAPI, HTTPException
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from routers.health import router as health_router
from routers.inception import router as inception_router
from routers.video import router as video_router
from routers.yolo import router as yolo_router
from services.video_service import GRADCAM_OUTPUT_DIR, OUTPUT_DIR
from routers.annotation import router as annotation_router
from routers import analysis
from routers.analysis import router as analysis_router



app = FastAPI(
    title = "AI Inference Server",
    version = "1.0.0"
)


app.mount(
    "/outputs/videos",
    StaticFiles(directory=str(OUTPUT_DIR)),
    name="output_videos",
)

# 처리된 동영상 파일은 기존 staticfiles 방식을 유지
# app.mount(
#     "/outputs/gradcam",
#     StaticFiles(
#         directory=str(GRADCAM_OUTPUT_DIR),
#     ),
#     name="output_gradcam",
# )

@app.get(
    "/outputs/gradcam/{path:path}",
    name="output_gradcam",
    response_class=FileResponse,
)
async def get_gradcam_image(
    path: str,
) -> FileResponse:
    """
    분석 과정에서 생성된 Grad-CAM PNG를
    브라우저와 React에 반환한다.
    """

    # Grad-CAM 파일이 저장되는 기준 폴더를 절대 경로로 변환한다.
    gradcam_root = GRADCAM_OUTPUT_DIR.resolve()

    # URL에서 받은 상대 경로를 실제 파일 경로로 변환한다.
    requested_file = (
        gradcam_root / path
    ).resolve()

    # ../ 등을 이용해 출력 폴더 밖의 파일에 접근하는 것을 차단한다.
    if (
        requested_file != gradcam_root
        and gradcam_root not in requested_file.parents
    ):
        raise HTTPException(
            status_code=400,
            detail="잘못된 Grad-CAM 파일 경로입니다.",
        )

    # 응답에 URL이 있더라도 실제 파일이 없으면 404를 반환한다.
    if not requested_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Grad-CAM 이미지 파일을 찾을 수 없습니다.",
        )

    # 브라우저에서 다운로드하지 않고 바로 이미지로 표시되도록 반환한다.
    return FileResponse(
        path=requested_file,
        media_type="image/png",
        filename=requested_file.name,
        content_disposition_type="inline",
    )


app.include_router(health_router) # # health.py에 정의된 /health API를 FastAPI 서버에 등록
app.include_router(inception_router)
app.include_router(video_router)
app.include_router(yolo_router)
app.include_router(annotation_router)
app.include_router(analysis_router)



# GET 요청을 처리하는 기본 API 경로uvicorn app:app --reload --port 8001
@app.get("/")
def root():
    return {
        "message": "AI Server is running",
    }
    


