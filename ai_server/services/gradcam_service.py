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


def create_thresholded_overlay(
    original_image: Image.Image,
    heatmap: np.ndarray,
    alpha: float = 0.50,
    activation_threshold: float = 0.25,
) -> Image.Image:
    """
    낮은 Grad-CAM 활성 영역은 투명하게 유지하고,
    임계값 이상의 영역만 원본 이미지에 합성한다.
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(
            "alpha 값은 0과 1 사이여야 합니다."
        )

    if not 0.0 <= activation_threshold <= 1.0:
        raise ValueError(
            "activation_threshold는 0과 1 사이여야 합니다."
        )

    original_rgb = original_image.convert("RGB")
    original_array = np.asarray(
        original_rgb,
        dtype=np.uint8,
    )

    resized_heatmap = cv2.resize(
        heatmap.astype(np.float32),
        (original_array.shape[1], original_array.shape[0]),
        interpolation=cv2.INTER_LINEAR,
    )

    heatmap_uint8 = np.uint8(
        np.clip(resized_heatmap, 0.0, 1.0) * 255
    )

    colored_bgr = cv2.applyColorMap(
        heatmap_uint8,
        cv2.COLORMAP_JET,
    )

    colored_rgb = cv2.cvtColor(
        colored_bgr,
        cv2.COLOR_BGR2RGB,
    ).astype(np.float32)

    original_float = original_array.astype(np.float32)

    activation_mask = (
        resized_heatmap >= activation_threshold
    ).astype(np.float32)

    # 활성도가 높을수록 더 선명하게 표시
    local_alpha = (
        alpha
        * resized_heatmap
        * activation_mask
    )[..., np.newaxis]

    overlay_array = (
        original_float * (1.0 - local_alpha)
        + colored_rgb * local_alpha
    )

    overlay_array = np.clip(
        overlay_array,
        0,
        255,
    ).astype(np.uint8)

    return Image.fromarray(
        overlay_array,
        mode="RGB",
    )

def create_transparent_heatmap(
    heatmap: np.ndarray,
    activation_threshold: float = 0.30,
    max_alpha: float = 0.75,
) -> Image.Image:
    """
    React에서 원본 영상 위에 겹칠 수 있도록
    투명 배경을 가진 RGBA Grad-CAM 이미지를 생성한다.

    활성도가 임계값보다 낮은 영역은 완전히 투명하게 처리하고,
    활성도가 높을수록 불투명도를 높인다.
    """
    if not 0.0 <= activation_threshold <= 1.0:
        raise ValueError(
            "activation_threshold는 0과 1 사이여야 합니다."
        )

    if not 0.0 <= max_alpha <= 1.0:
        raise ValueError(
            "max_alpha는 0과 1 사이여야 합니다."
        )

    normalized_heatmap = np.clip(
        heatmap.astype(np.float32),
        0.0,
        1.0,
    )

    heatmap_uint8 = np.uint8(
        normalized_heatmap * 255
    )

    colored_bgr = cv2.applyColorMap(
        heatmap_uint8,
        cv2.COLORMAP_JET,
    )

    colored_rgb = cv2.cvtColor(
        colored_bgr,
        cv2.COLOR_BGR2RGB,
    )

    alpha_mask = np.where(
        normalized_heatmap >= activation_threshold,
        normalized_heatmap * max_alpha,
        0.0,
    )

    alpha_uint8 = np.uint8(
        np.clip(alpha_mask, 0.0, 1.0) * 255
    )

    rgba_array = np.dstack(
        (
            colored_rgb,
            alpha_uint8,
        )
    )

    return Image.fromarray(
        rgba_array,
        mode="RGBA",
    )

def generate_gradcam_data(
    image: Image.Image,
    target_class: int | None = None,
    alpha: float = 0.45,
    always_show: bool = False,
) -> dict[str, object]:
    """
    한 번의 모델 forward와 backward로 예측값과 Grad-CAM을 생성한다.

    이미지 API에서는 기존 정책에 따라 Stenosis 예측일 때만
    Grad-CAM을 표시할 수 있고, 동영상 처리에서는 always_show=True로
    지정하여 예측 결과와 관계없이 협착 클래스 기준 Grad-CAM을 만든다.

    Base64 변환 전의 PIL 이미지도 반환하므로 동영상 처리 과정에서
    불필요한 PNG 인코딩과 디코딩을 피할 수 있다.
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(
            "alpha 값은 0과 1 사이여야 합니다."
        )

    original_image = image.convert("RGB")

    input_tensor = inception_transform(original_image)
    input_tensor = input_tensor.unsqueeze(0)
    input_tensor = input_tensor.to(DEVICE)

    target_layer = inception_model.model.Mixed_7c

    gradcam = GradCAM(
        model=inception_model,
        target_layer=target_layer,
    )

    try:
        result = gradcam.generate(
            input_tensor=input_tensor,
            target_class=target_class,
        )

        show_gradcam = (
            always_show
            or result["predicted_label"] == "Stenosis"
        )

        heatmap_image: Image.Image | None = None
        overlay_image: Image.Image | None = None
        transparent_heatmap_image: Image.Image | None = None

        if show_gradcam:
            heatmap_image = create_colored_heatmap(
                result["heatmap"]
            )

            overlay_image = create_thresholded_overlay(
                original_image=original_image,
                heatmap=result["heatmap"],
                alpha = alpha,
                activation_threshold = 0.30,
            )
            
            transparent_heatmap_image = (
                create_transparent_heatmap(
                    heatmap=result["heatmap"],
                    activation_threshold=0.30,
                    max_alpha=0.75,
                )
            )
            

        return {
            "predicted_class": result["predicted_class"],
            "predicted_label": result["predicted_label"],
            "target_class": result["target_class"],
            "target_label": result["target_label"],
            "confidence": result["confidence"],
            "probabilities": result["probabilities"],
            "show_gradcam": show_gradcam,
            "heatmap": result["heatmap"],
            "heatmap_image": heatmap_image,
            "overlay_image": overlay_image,
            "transparent_heatmap_image": (
                transparent_heatmap_image
            ),
        }

    finally:
        gradcam.remove_hooks()
    
def image_to_base64(image: Image.Image) -> str:
    
    buffer = BytesIO()
    image.save(buffer, format = "PNG")
    
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def generate_gradcam(
    image: Image.Image,
    target_class: int | None = None,
    alpha: float = 0.45,
    always_show: bool = False,
) -> dict[str, object]:
    """
    이미지 API에서 사용할 Grad-CAM 결과를 Base64 문자열로 반환한다.

    기본값에서는 기존 동작과 동일하게 Stenosis 예측일 때만
    Grad-CAM 이미지를 반환한다.
    """
    result = generate_gradcam_data(
        image=image,
        target_class=target_class,
        alpha=alpha,
        always_show=always_show,
    )

    heatmap_image = result["heatmap_image"]
    overlay_image = result["overlay_image"]

    heatmap_base64 = (
        image_to_base64(heatmap_image)
        if heatmap_image is not None
        else None
    )

    overlay_base64 = (
        image_to_base64(overlay_image)
        if overlay_image is not None
        else None
    )

    return {
        "predicted_class": result["predicted_class"],
        "predicted_label": result["predicted_label"],
        "target_class": result["target_class"],
        "target_label": result["target_label"],
        "confidence": result["confidence"],
        "probabilities": result["probabilities"],
        "show_gradcam": result["show_gradcam"],
        "heatmap_base64": heatmap_base64,
        "overlay_base64": overlay_base64,
    }
