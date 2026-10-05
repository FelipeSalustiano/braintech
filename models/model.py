import torch
from torch import nn


class MeterNetwork(nn.Module):
    """
    Rede neural para detectar medidores.

    Saída por célula:
        0 -> posição X
        1 -> posição Y
        2 -> largura
        3 -> altura
        4 -> confiança/objectness
    """

    def __init__(self):
        super().__init__()

        self.features = nn.Sequential(

            # 1ª camada
            nn.Conv2d(
                in_channels=1,
                out_channels=32,
                kernel_size=3,
                padding=1
            ),
            nn.ReLU(),
            nn.MaxPool2d(2),

            # 2ª camada
            nn.Conv2d(
                in_channels=32,
                out_channels=64,
                kernel_size=3,
                padding=1
            ),
            nn.ReLU(),
            nn.MaxPool2d(2),

            # 3ª camada
            nn.Conv2d(
                in_channels=64,
                out_channels=128,
                kernel_size=3,
                padding=1
            ),
            nn.ReLU(),
            nn.MaxPool2d(2),

            # 4ª camada
            nn.Conv2d(
                in_channels=128,
                out_channels=256,
                kernel_size=3,
                padding=1
            ),
            nn.ReLU()
        )

        self.head = nn.Conv2d(
            in_channels=256,
            out_channels=5,
            kernel_size=1
        )

    def forward(self, x):
        x = self.features(x)
        x = self.head(x)

        return x