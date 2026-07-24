from pathlib import Path
from PIL import Image
from services.inception_service import predict

# 테스트 

BASE_DIR = Path(__file__).resolve().parent

# 테스트 이미지 경로
IMAGE_PATHS = [BASE_DIR/ "test_images" / "test_frame_1.png",
              BASE_DIR/"test_images" / "test_frame_2.png",]
              


def main():
    for image_path in IMAGE_PATHS:
        if not image_path.exists():
            raise FileNotFoundError(f"테스트 이미지를 찾을 수 없습니다: {image_path}")
        with Image.open(image_path) as image:
            result = predict(image)

        print("=" * 50)
        print("InceptionV3 예측 결과:")
        print(f"파일명: {image_path.name}")
        print(f"예측 클래스: {result['predicted_class']}")
        print(f"예측 결과 : {result['predicted_label']}")
        print(f"신뢰도: {result['confidence']*100:.2f}%")
        print(f"정상 확률: {result['probabilities']['normal']*100:.2f}%")
        print(f"협착 확률: {result['probabilities']['stenosis']*100:.2f}%")  
        print("=" * 50)

if __name__ == "__main__":
    main()




