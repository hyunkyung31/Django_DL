import torch.nn as nn
from torchvision import models


class InceptionV3Binary(nn.Module):
    def __init__(self, pretrained=True):
        super(InceptionV3Binary, self).__init__()

        self.model = models.inception_v3(
            weights=(
                models.Inception_V3_Weights.DEFAULT
                if pretrained
                else None
            ),
            init_weights = False # 저장된 가중치 불러오는 환경이므로 새 가중치 초기화할 필요 없음 
        )

        self.model.aux_logits = False

        num_ftrs = self.model.fc.in_features

        self.model.fc = nn.Linear(num_ftrs, 2,)

    def forward(self, x):
        return self.model(x)