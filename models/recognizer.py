"""Reconhecedor da leitura no recorte do display: CNN + BiLSTM com 6 saídas fixas.

A leitura é um número de até 6 dígitos alinhado à direita no display, então a
rede classifica 6 posições fixas (0-9 cada), com o rótulo completado com zeros
à esquerda ("4939" -> "004939"). Os zeros iniciais do display viram rótulo de
verdade, em vez de algo a ignorar.

Uma segunda saída estima se o display está ilegível (borrado, escuro, reflexo).
Ela só aprende com as fotos conferidas à mão; nas outras, o rótulo é desconhecido.

Testamos CTC antes: com o rótulo sem zeros à esquerda (é o que os CSVs trazem),
a rede ficava presa emitindo só "vazio" por dezenas de épocas. Com as 6 saídas
fixas e entropia cruzada, o mesmo subconjunto converge em 20 épocas.
"""

from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset
from torchvision.transforms import v2

NUM_DIGITS = 6
IMAGE_HEIGHT = 48
IMAGE_WIDTH = 160


def encode(label: str) -> list[int]:
    return [int(char) for char in label.zfill(NUM_DIGITS)]


def load_display(path: Path) -> np.ndarray:
    """Recorte do display em tons de cinza, esticado para o tamanho de entrada da rede."""
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Display crop not found: {path}")
    return cv2.resize(image, (IMAGE_WIDTH, IMAGE_HEIGHT), interpolation=cv2.INTER_AREA)


def train_transform() -> v2.Compose:
    """Imita a variação real: caixa do detector deslocada, foto borrada, escura ou estourada."""
    return v2.Compose([
        v2.RandomAffine(degrees=3, translate=(0.04, 0.08), scale=(0.9, 1.08), shear=5),
        v2.ColorJitter(brightness=0.5, contrast=0.5),
        v2.RandomApply([v2.GaussianBlur(kernel_size=5, sigma=(0.1, 1.5))], p=0.3),
        v2.ToDtype(torch.float32, scale=True),
    ])


def eval_transform() -> v2.Compose:
    return v2.Compose([v2.ToDtype(torch.float32, scale=True)])


class DisplayDataset(Dataset):
    """Recortes de display já carregados em memória (cabem fácil: 48 x 160 cada).

    Rótulo "" quer dizer leitura desconhecida (foto ilegível); `illegible` é 1, 0
    ou NaN quando ninguém conferiu a foto.
    """

    def __init__(self, images: list[np.ndarray], labels: list[str] | None = None, transform=None, illegible: list[float] | None = None):
        self.images = images
        self.labels = labels
        self.illegible = illegible
        self.transform = transform or eval_transform()

    def __len__(self):
        return len(self.images)

    def __getitem__(self, index):
        image = self.transform(torch.from_numpy(self.images[index])[None])
        # Normaliza por imagem: o brilho do display varia muito entre fotos
        image = (image - image.mean()) / (image.std() + 1e-6)
        label = self.labels[index] if self.labels is not None else "0"
        illegible = self.illegible[index] if self.illegible is not None else float("nan")
        return image, label, illegible


def collate(batch):
    images, labels, illegible = zip(*batch)
    targets = torch.tensor([encode(label or "0") for label in labels], dtype=torch.long)
    return torch.stack(images), targets, list(labels), torch.tensor(illegible, dtype=torch.float32)


def _conv(in_channels: int, out_channels: int) -> list[nn.Module]:
    return [nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False), nn.BatchNorm2d(out_channels), nn.ReLU(inplace=True)]


class MeterReader(nn.Module):
    """CNN estilo VGG que reduz a altura a 1 (40 colunas), BiLSTM e uma cabeça por posição."""

    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            *_conv(1, 64), nn.MaxPool2d(2),               # 24 x 80
            *_conv(64, 128), nn.MaxPool2d(2),             # 12 x 40
            *_conv(128, 256), *_conv(256, 256),
            nn.MaxPool2d((2, 1)),                         # 6 x 40
            *_conv(256, 384), *_conv(384, 384),
            nn.MaxPool2d((2, 1)),                         # 3 x 40
            nn.Conv2d(384, 384, (3, 1), bias=False),      # 1 x 40
            nn.BatchNorm2d(384),
            nn.ReLU(inplace=True),
        )
        self.rnn = nn.LSTM(384, 192, num_layers=2, bidirectional=True, batch_first=True, dropout=0.2)
        # Achatar as 40 colunas mantém a posição horizontal, que diz qual dígito é qual
        self.head = nn.Sequential(nn.Dropout(0.3), nn.Linear(40 * 384, NUM_DIGITS * 10))
        self.legibility = nn.Sequential(nn.Dropout(0.3), nn.Linear(40 * 384, 1))

    def forward(self, x):
        """Logits dos dígitos (N, 6, 10) e logit de foto ilegível (N,)."""
        features = self.features(x).squeeze(2).permute(0, 2, 1)  # (N, 40, 384)
        features, _ = self.rnn(features)
        features = features.flatten(1)
        # detach: com o gradiente da legibilidade, os dígitos não saíam do platô inicial
        # (acerto de validação < 2% em 40 épocas); assim ela só lê o que os dígitos aprenderam
        return self.head(features).view(-1, NUM_DIGITS, 10), self.legibility(features.detach()).squeeze(1)


def decode(logits: torch.Tensor) -> list[tuple[str, float]]:
    """Leitura sem zeros à esquerda e confiança.

    A confiança é a menor probabilidade entre as 6 posições: basta um dígito
    duvidoso para a leitura toda ser duvidosa.
    """
    probability, digits = logits.softmax(-1).max(-1)
    return [
        (str(int("".join(map(str, row)))), min(scores))
        for row, scores in zip(digits.tolist(), probability.tolist())
    ]


def load_recognizer(checkpoint_path: Path, device) -> nn.Module:
    model = MeterReader()
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])
    return model.to(device).eval()


@torch.inference_mode()
def recognize(model, images: list[np.ndarray], device, batch_size: int = 256) -> list[tuple[str, float, float]]:
    """(leitura, confiança, probabilidade de ilegível) de cada recorte."""
    loader = torch.utils.data.DataLoader(DisplayDataset(images), batch_size=batch_size, collate_fn=collate)
    results = []
    for batch, _, _, _ in loader:
        logits, illegible = model(batch.to(device))
        probabilities = illegible.float().sigmoid().cpu().tolist()
        results += [(text, score, p) for (text, score), p in zip(decode(logits.float().cpu()), probabilities)]
    return results
