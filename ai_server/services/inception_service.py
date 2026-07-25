from pathlib import Path
import torch
from model_defs.inception import InceptionV3Binary
from PIL import Image
from utils.transforms import inception_transform
import torch.nn.functional as F

CURRENT_FILE = Path(__file__).resolve()

# ai_server 파일 경로
BASE_DIR = CURRENT_FILE.parent.parent

# 가중치 파일 경로
MODEL_PATH = BASE_DIR / "models" / "best_inception_stenosis.pth"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

CLASS_NAMES = {0: "Normal", 1: "Stenosis"}

# InceptionV3 모델 구조를 생성하고 학습된 가중치 불러오는 함수
def load_inception_model() -> InceptionV3Binary:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"InceptionV3 가중치 파일을 찾을 수 없습니다: {MODEL_PATH}")
    
    # 모델클래스 분리 시 - 기존 학습코드 pretrained=True 유지한 상태 - ImageNet 가중치로드 False
    model = InceptionV3Binary(pretrained=False)
    
    # GPU, CPU 환경에 맞게 가중치 로드
    state_dict = torch.load(MODEL_PATH, map_location=DEVICE,)
    
    # 모델구조와 저장된 가중치 일치하는지 검사 strict = True
    model.load_state_dict(state_dict, strict = True, )
    
    model.to(DEVICE)
    
    # 추론 모드로 전환
    model.eval()
    
    return model

# 이 모듈이 처음 import될 때 모델을 한 번만 로드
inception_model = load_inception_model()


def predict(image: Image.Image):
    image = image.convert("RGB") # 3채널 변환
    input_tensor = inception_transform(image) # 학습과 동일한 전처리를 적용하여 Tensor 생성
    input_tensor = input_tensor.unsqueeze(0) # 배치 추가
    input_tensor = input_tensor.to(DEVICE)
    
    with torch.no_grad():
        outputs = inception_model(input_tensor)
        probabilities = F.softmax(outputs, dim = 1)
        confidence, predicted = torch.max(probabilities, dim = 1,)
    predicted_class = int(predicted.item())
    normal_probability = float(probabilities[0][0].item())
    stenosis_probability = float(probabilities[0][1].item())
    
    return {
        
        "predicted_class": predicted_class,
        "predicted_label": CLASS_NAMES[predicted_class],
        "confidence": float(confidence.item()),
        "probabilities": {
            "normal": normal_probability,
            "stenosis": stenosis_probability,
        }
    }