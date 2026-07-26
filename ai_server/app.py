from fastapi import FastAPI
from routers.health import router as health_router
from routers.inception import router as inception_router
from routers.video import router as video_router
from routers.yolo import router as yolo_router
from fastapi.staticfiles import StaticFiles
from services.video_service import GRADCAM_OUTPUT_DIR, OUTPUT_DIR
from routers.annotation import router as annotation_router


app = FastAPI(
    title = "AI Inference Server",
    version = "1.0.0"
)


app.mount(
    "/outputs/videos",
    StaticFiles(directory=str(OUTPUT_DIR)),
    name="output_videos",
)

app.mount(
    "/outputs/gradcam",
    StaticFiles(
        directory=str(GRADCAM_OUTPUT_DIR),
    ),
    name="output_gradcam",
)


app.include_router(health_router) # # health.py에 정의된 /health API를 FastAPI 서버에 등록
app.include_router(inception_router)
app.include_router(video_router)
app.include_router(yolo_router)
app.include_router(annotation_router)

# GET 요청을 처리하는 기본 API 경로uvicorn app:app --reload --port 8001
@app.get("/")
def root():
    return {
        "message": "AI Server is running",
    }
    


