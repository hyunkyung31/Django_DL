import base64
from pathlib import Path
from PIL import Image
from services.gradcam_service import generate_gradcam

BASE_DIR = Path(__file__).resolve().parent
TEST_IMAGE_DIR = BASE_DIR / "test_images"
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(parents = True, exist_ok = True)
TEST_IMAGE_NAMES = [
    "test_frame_1.png",
    "test_frame_2.png",
]

def save_base64_image(base64_string: str, output_path: Path) -> None:
    image_bytes = base64.b64decode(base64_string)
    output_path.write_bytes(image_bytes)
    
def main():
    for image_name in TEST_IMAGE_NAMES:
        image_path = TEST_IMAGE_DIR / image_name
        
        if not image_path.exists():
            print(f"[건너뜀] 테스트 이미지를 찾을 수 없습니다: {image_path}")
            continue
        
        image = Image.open(image_path)
        
        result = generate_gradcam(image = image,
                                  target_class = None,
                                  alpha = 0.45,)
        image_stem = image_path.stem
        
        heatmap_path = OUTPUT_DIR / f"{image_stem}_gradcam_heatmap.png"
        overlay_path = OUTPUT_DIR / f"{image_stem}_gradcam_overlay.png"
        
        print()
        print(f"==={image_name} Grad-CAM 결과 ===")
        print("예측 클래스", result["predicted_class"])
        print("예측 결과", result["predicted_label"])
        print("Grad-CAM 기준 클래스", result["target_label"])
        print("신뢰도", result["confidence"])
        print("확률", result["probabilities"]["normal"])
        print("확률", result["probabilities"]["stenosis"])
        
        if result["show_gradcam"]:
            save_base64_image(result["heatmap_base64"], heatmap_path)
            save_base64_image(result["overlay_base64"], overlay_path)
            
            print("저장경로", heatmap_path)
            print("저장경로", overlay_path)
        else:
            print("Normal 예측이므로 GradCAM을 저장하지 않습니다.")
        


if __name__ == "__main__":
    main()