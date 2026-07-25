from fastapi import FastAPI
from routers.health import router as health_router
from routers.inception import router as inception_router

app = FastAPI(
    title = "AI Inference Server",
    version = "1.0.0"
)
app.include_router(health_router) # # health.py에 정의된 /health API를 FastAPI 서버에 등록
app.include_router(inception_router)

# GET 요청을 처리하는 기본 API 경로
@app.get("/")
def root():
    return {
        "message": "AI Server is running",
    }
    


