from torch import nn


class MeterNetwork(nn.Module):
    """
    Modelo de Rede Neural para identificar medidores em imagens
    """

    def __init__(self):
        super().__init__()

        self.features = nn.Sequential(
            # 1ª camada
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),

            # 2ª camada
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),

            # 3ª camada
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),

            # 4ª camada
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.ReLU()
        )

        self.head = nn.Conv2d(
            256,
            5, # x, y, altura e largura
            kernel_size=1
        )

    def forward(self, x):
        x = self.features(x)
        x = self.head(x)

        return x