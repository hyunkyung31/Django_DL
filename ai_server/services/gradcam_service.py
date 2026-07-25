import base64
from io import BytesIO
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
import cv2

from services.inception_service import (
    CLASS_NAMES,
    DEVICE,
    inception_model,
)
from utils.transforms import inception_transform


class GradCAM:
    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module):
        self.model = model
        self.target_layer = target_layer
        self.activations = None
        self.gradients = None
        
        self.forward_handle = self.target_layer.register_forward_hook(self._save_activations)
        self.backward_handle = self.target_layer.register_full_backward_hook(self._save_gradients)
    
    def _save_activations(self, module, inputs, output):
        self.activations = output.detach()
    
    def _save_gradients(self, module, grad_imput, grad_output):
        self.gradients = grad_output[0].detach()
    
    def generate(self,
                 input_tensor: torch.Tensor,
                 target_class: int | None = None,):
        self.model.zero_grad(set_to_none = True)
        outputs = self.model(input_tensor)
        
        probabilities = F.softmax(outputs, dim = 1)
        confidence, predicted = torch.max(probabilities, dim = 1)
        
        predicted_class = int(predicted.item())
        
        if target_class is None:
            target_class = predicted_class
        
        if target_class not in CLASS_NAMES:
            raise ValueError(f"지원하지 않는 클래스 번호입니다: {target_class}")
        
        target_score = outputs[0, target_class]
        target_score.backward()
        
        if self.activations is None:
            raise RuntimeError("Grad-CAM 특징 맵을 가져오지 못했습니다.")
        if self.gradients is None:
            raise RuntimeError("Grad-CAM 기울기를 가져오지 못했습니다.")
        
        weights = self.gradients.mean(dim=(2, 3), keepdim = True)
        cam = torch.sum(weights * self.activations, dim = 1)
        cam = F.relu(cam)
        
        cam = F.interpolate(cam.unsqueeze(1),
                            size = (299, 299),
                            mode = "bilinear",
                            align_corners = False)
        cam = cam.squeeze()
        
        cam_min = cam.min()
        cam_max = cam.max()
        
        if float(cam_max - cam_min) > 0:
            cam = (cam - cam_min) / (cam_max - cam_min)
        else:
            cam = torch.zeros_like(cam)
        heatmap = cam.detach().cpu().numpy()
        
        return {
            "heatmap": heatmap,
            "predicted_class": predicted_class,
            "predicted_label": CLASS_NAMES[predicted_class],
            "target_class": target_class,
            "target_label": CLASS_NAMES[target_class],
            "confidence": float(confidence.item()),
            "probabilities": {
                "normal":float(probabilities[0, 0].item()),
                "stenosis": float(probabilities[0, 1].item()),
            },
        }
    def remove_hooks(self):
        self.forward_handle.remove()
        self.backward_handle.remove()

def create_colored_heatmap(
    heatmap: np.ndarray,
) -> Image.Image:
    heatmap = np.clip(heatmap, 0.0, 1.0)

    heatmap_uint8 = np.uint8(255 * heatmap)

    # OpenCV 결과는 BGR 형식
    colored_bgr = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET,)

    # PIL에서 사용할 수 있도록 RGB로 변환
    colored_rgb = cv2.cvtColor(colored_bgr, cv2.COLOR_BGR2RGB,)

    return Image.fromarray(colored_rgb, mode="RGB",)

def create_overlay(
    original_image: Image.Image,
    heatmap_image: Image.Image,
    alpha: float = 0.45,
) -> Image.Image:

    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha 값은 0과 1 사이여야 합니다.")

    original_image = original_image.convert("RGB")
    original_image = original_image.resize(heatmap_image.size,Image.Resampling.BILINEAR,)

    original_array = np.asarray(original_image, dtype=np.uint8,)

    heatmap_array = np.asarray(heatmap_image, dtype=np.uint8,)

    overlay_array = cv2.addWeighted(original_array,
                                    1.0 - alpha,
                                    heatmap_array,
                                    alpha,
                                    0,)

    return Image.fromarray(overlay_array, mode="RGB")


    
def image_to_base64(image: Image.Image) -> str:
    
    buffer = BytesIO()
    image.save(buffer, format = "PNG")
    
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def generate_gradcam(
    image: Image.Image,
    target_class: int | None = None,
    alpha: float = 0.45,
):
    
    original_image = image.convert("RGB")
    
    input_tensor = inception_transform(original_image)
    input_tensor = input_tensor.unsqueeze(0)
    input_tensor = input_tensor.to(DEVICE)
    
    target_layer = inception_model.model.Mixed_7c
    gradcam = GradCAM(model = inception_model,
                      target_layer = target_layer,)
    
    try:
        result = gradcam.generate(input_tensor = input_tensor,
                                  target_class = target_class,)
        # Stenosis로 예측된 경우에만 Grad-CAM 표시
        
        show_gradcam = result["predicted_label"] == "Stenosis"
        heatmap_base64 = None
        overlay_base64 = None
        
        if show_gradcam:
            heatmap_image = create_colored_heatmap(result["heatmap"])
            overlay_image = create_overlay(original_image = original_image,
                                           heatmap_image = heatmap_image,
                                           alpha = alpha,)
            
            heatmap_base64 = image_to_base64(heatmap_image)
            overlay_base64 = image_to_base64(overlay_image)
        

        return {
            "predicted_class": result["predicted_class"],
            "predicted_label": result["predicted_label"],
            "target_class": result["target_class"],
            "target_label": result["target_label"],
            "confidence": result["confidence"],
            "probabilities": result["probabilities"],
            "show_gradcam": show_gradcam,
            "heatmap_base64": heatmap_base64,
            "overlay_base64": heatmap_base64,

        }
    finally:
        # 요청마다 생성된 hook이 누적되지 않도록 제거
        gradcam.remove_hooks()