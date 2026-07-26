from io import BytesIO
from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from services.inception_service import predict
from  services.gradcam_service import generate_gradcam

router = APIRouter(
    prefix = "/inception",
    tags = ["InceptionV3"],
)

ALLOWED_CONTENT_TYPES = {"image/png",
                         "image/jpg",
                         "image/jpeg",}

@router.post("/predict")
async def predict_inception(
    file: UploadFile = File(...), # 파일 필수
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail = (
                "지원하지 않는 파일 형식입니다."
                "PNG, JPG, JPEG 이미지만 업로드할 수 있습니다."
            ),
        )
        
    try:
        file_bytes = await file.read()
        
        with Image.open(BytesIO(file_bytes)) as image:
            result = predict(image)
            
    except UnidentifiedImageError:
        raise HTTPException(
            status_code = 400,
            detail = "올바른 이미지 파일이 아닙니다."
        )
    except Exception as error:
        raise HTTPException(
            status_code = 500,
            detail = f"InceptionV3 추론 중 오류가 발생했습니다: {error}",
        )
    return {
        "filename": file.filename,
        **result,
    }

@router.post("/gradcam")
async def predict_inception_gradcam(
    file: UploadFile = File(...),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code = 400,
            detail = ("지원하지 않는 파일 형식입니다."
                      "PNG, JPG,JPEG"
        ),
     )
    try:
        file_bytes = await file.read()
        
        with Image.open(BytesIO(file_bytes)) as image:
            result = generate_gradcam(image = image,
                                      target_class = None,
                                      alpha = 0.45,)
    except UnidentifiedImageError:
        raise HTTPException(status_code = 400,
                            detail = "올바른 이미지 파일이 아닙니다.")
    except Exception as error:
        raise HTTPException(status_code = 500,
                            detail = f"InceptionV3 Grad-CAM 처리 중 오류가 발생했습니다: {error}",)
    return {
        "filename": file.filename,
        **result,
    }
            