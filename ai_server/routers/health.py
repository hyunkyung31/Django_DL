# 같은 경로를 가진 API 경로들을 별도 파일에서 묶어서 관리하는 FASTAPI Class
from fastapi import APIRouter

router = APIRouter(
    tags=["Health"],
)


# 서버의 상태를 확인하는 전용 API    
@router.get("/health")
def health_check():
    return {
        # 모델 연결 후 추가
        "status": "ok"
    }