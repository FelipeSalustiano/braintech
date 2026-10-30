"""
Regras de recorte da região do medidor a partir da caixa prevista pelo detector.

Este módulo não depende do PyTorch: recebe a caixa já decodificada (valores
normalizados entre 0 e 1) e devolve as coordenadas em pixels do recorte, junto
com um status que diz se o recorte é confiável para a etapa de OCR.
"""

from dataclasses import dataclass

from PIL import Image

# Status possíveis de cada foto após a etapa de recorte.
STATUS_RECORTADO = "recortado"            # recorte válido, segue para o OCR
STATUS_CAIXA_CORTADA = "caixa_cortada"    # parte da caixa ficou fora da foto
STATUS_SEM_DETECCAO = "sem_deteccao"      # score abaixo do limiar
STATUS_CAIXA_INVALIDA = "caixa_invalida"  # caixa pequena demais para ler


@dataclass
class CropResult:
    status: str
    score: float | None = None
    left: int | None = None
    top: int | None = None
    right: int | None = None
    bottom: int | None = None
    outside_ratio: float = 0.0


def compute_crop_box(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    score: float,
    image_size: tuple[int, int],
    margin: float = 0.10,
    min_size: int = 32,
    max_outside_ratio: float = 0.15,
) -> CropResult:
    """
    Converte a caixa normalizada em um recorte em pixels.

    Parâmetros:
        center_x, center_y, width, height: caixa normalizada (0 a 1).
        score: confiança da detecção.
        image_size: (largura, altura) da imagem que será recortada.
        margin: folga adicionada em cada lado, como fração do tamanho da
            caixa (0.10 = 10%), para não cortar dígitos na borda.
        min_size: menor largura/altura aceitável do recorte, em pixels.
        max_outside_ratio: fração máxima da caixa (com margem) que pode
            ficar fora da imagem antes de marcar o recorte como cortado.
    """
    image_width, image_height = image_size

    # Caixa em pixels, já com a margem aplicada em cada lado.
    box_width = width * image_width * (1 + 2 * margin)
    box_height = height * image_height * (1 + 2 * margin)
    raw_left = center_x * image_width - box_width / 2
    raw_top = center_y * image_height - box_height / 2
    raw_right = raw_left + box_width
    raw_bottom = raw_top + box_height

    # Ajusta a caixa aos limites da imagem.
    left = max(0, int(round(raw_left)))
    top = max(0, int(round(raw_top)))
    right = min(image_width, int(round(raw_right)))
    bottom = min(image_height, int(round(raw_bottom)))

    crop_width = right - left
    crop_height = bottom - top
    if crop_width < min_size or crop_height < min_size:
        return CropResult(status=STATUS_CAIXA_INVALIDA, score=score)

    # Quanto da caixa ficou fora da imagem (0 = nada, 1 = tudo).
    raw_area = max(box_width * box_height, 1e-6)
    outside_ratio = 1 - (crop_width * crop_height) / raw_area
    outside_ratio = max(0.0, outside_ratio)

    status = STATUS_RECORTADO
    if outside_ratio > max_outside_ratio:
        status = STATUS_CAIXA_CORTADA

    return CropResult(
        status=status,
        score=score,
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        outside_ratio=outside_ratio,
    )


def crop_image(image: Image.Image, result: CropResult) -> Image.Image:
    """Recorta a imagem usando as coordenadas calculadas em compute_crop_box."""
    return image.crop((result.left, result.top, result.right, result.bottom))
