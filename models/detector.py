"""Detector Faster R-CNN e dataset genérico usados no treino semi-supervisionado."""

import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import tv_tensors
from torchvision.models.detection import (
    FasterRCNN_ResNet50_FPN_V2_Weights,
    fasterrcnn_resnet50_fpn_v2,
)
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.ops import box_iou, nms
from torchvision.transforms import v2

CLASS_NAMES = ["Medidor"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def build_detector(pretrained: bool = True) -> torch.nn.Module:
    """Faster R-CNN v2 com backbone pré-treinado no COCO e cabeça de 1 classe."""
    weights = FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT if pretrained else None
    model = fasterrcnn_resnet50_fpn_v2(
        weights=weights,
        # As fotos são 360 x 480; um leve upscale ajuda nas caixas pequenas
        min_size=480,
        max_size=640,
        box_detections_per_img=10,
    )
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    # +1 por causa da classe de fundo
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, len(CLASS_NAMES) + 1)
    return model


def load_detector(checkpoint_path: Path, device) -> torch.nn.Module:
    model = build_detector(pretrained=False)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])
    return model.to(device).eval()


def load_coco_samples(json_path: Path, image_dir: Path) -> list[dict]:
    """Lê um COCO e devolve amostras {path, boxes (xyxy)}.

    Imagens sem anotação viram amostras negativas (boxes vazio): no dataset
    rotulado elas são fotos sem medidor identificável.
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    boxes_by_image = {image["id"]: [] for image in data["images"]}
    for annotation in data["annotations"]:
        x, y, w, h = annotation["bbox"]
        if w > 1 and h > 1:
            boxes_by_image[annotation["image_id"]].append([x, y, x + w, y + h])

    return [
        {
            "image_id": image["id"],
            "path": Path(image_dir) / image["file_name"],
            "boxes": np.array(boxes_by_image[image["id"]], dtype=np.float32).reshape(-1, 4),
        }
        for image in data["images"]
    ]


def list_images(folder: Path) -> list[Path]:
    return sorted(
        path for path in Path(folder).iterdir()
        if path.suffix.lower() in IMAGE_EXTENSIONS
    )


def train_transform() -> v2.Compose:
    """Augmentação "ruidosa" do aluno (Noisy Student): geometria leve + fotometria forte."""
    return v2.Compose([
        v2.RandomHorizontalFlip(p=0.5),
        v2.RandomApply([v2.RandomAffine(degrees=5, translate=(0.05, 0.05), scale=(0.8, 1.15))], p=0.5),
        v2.ColorJitter(brightness=0.4, contrast=0.4),
        v2.RandomApply([v2.GaussianBlur(kernel_size=5, sigma=(0.1, 2.0))], p=0.2),
        v2.ToDtype(torch.float32, scale=True),
        v2.SanitizeBoundingBoxes(min_size=4),
    ])


def eval_transform() -> v2.Compose:
    return v2.Compose([v2.ToDtype(torch.float32, scale=True)])


def read_image(path: Path) -> tv_tensors.Image:
    # As fotos são em tons de cinza; o backbone pré-treinado espera 3 canais
    image = np.array(Image.open(path).convert("RGB"))
    return tv_tensors.Image(torch.from_numpy(image).permute(2, 0, 1))


class DetectionDataset(Dataset):
    """Dataset de detecção a partir de amostras {path, boxes}, reais ou pseudo-rotuladas."""

    def __init__(self, samples: list[dict], transform=None):
        self.samples = samples
        self.transform = transform or eval_transform()

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        sample = self.samples[index]
        image = read_image(sample["path"])
        boxes = tv_tensors.BoundingBoxes(
            torch.as_tensor(sample["boxes"], dtype=torch.float32).reshape(-1, 4),
            format="XYXY",
            canvas_size=image.shape[-2:],
        )
        target = {"boxes": boxes, "labels": torch.ones(len(boxes), dtype=torch.int64)}
        image, target = self.transform(image, target)
        target["boxes"] = target["boxes"].as_subclass(torch.Tensor)
        return image.as_subclass(torch.Tensor), target


class ImageFolderDataset(Dataset):
    """Imagens sem rótulo, para inferência."""

    def __init__(self, paths: list[Path]):
        self.paths = paths

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, index):
        image = read_image(self.paths[index])
        return image.as_subclass(torch.Tensor).float() / 255.0, index


def collate(batch):
    return tuple(zip(*batch))


def _merge_tta(original: dict, flipped: dict, match_iou: float = 0.6) -> tuple[torch.Tensor, torch.Tensor]:
    """Combina predições da imagem original e espelhada.

    Caixas que aparecem nas duas visões têm coordenadas e scores médios;
    caixas vistas em uma só visão têm o score pela metade (inconsistência).
    """
    boxes_a, scores_a = original["boxes"], original["scores"]
    boxes_b, scores_b = flipped["boxes"], flipped["scores"]
    if len(boxes_a) == 0 or len(boxes_b) == 0:
        boxes = torch.cat([boxes_a, boxes_b])
        return boxes, torch.cat([scores_a, scores_b]) / 2

    iou = box_iou(boxes_a, boxes_b)
    best_iou, best_index = iou.max(dim=1)
    merged_boxes, merged_scores = [], []
    used_b = torch.zeros(len(boxes_b), dtype=torch.bool, device=boxes_b.device)

    for i in range(len(boxes_a)):
        j = best_index[i]
        if best_iou[i] >= match_iou and not used_b[j]:
            used_b[j] = True
            weights = torch.stack([scores_a[i], scores_b[j]])
            box = (boxes_a[i] * weights[0] + boxes_b[j] * weights[1]) / weights.sum()
            merged_boxes.append(box)
            merged_scores.append(weights.mean())
        else:
            merged_boxes.append(boxes_a[i])
            merged_scores.append(scores_a[i] / 2)

    for j in torch.nonzero(~used_b).flatten():
        merged_boxes.append(boxes_b[j])
        merged_scores.append(scores_b[j] / 2)

    return torch.stack(merged_boxes), torch.stack(merged_scores)


def suppress_nested(boxes: torch.Tensor, scores: torch.Tensor, overlap: float = 0.8) -> tuple[torch.Tensor, torch.Tensor]:
    """Remove caixas aninhadas em uma caixa de score maior.

    O modelo às vezes propõe o medidor e também o gabinete que o contém. O NMS
    não pega esse caso (IoU baixo), mas a interseção cobre quase toda a caixa menor.
    """
    if len(boxes) < 2:
        return boxes, scores
    order = scores.argsort(descending=True)
    boxes, scores = boxes[order], scores[order]
    areas = (boxes[:, 2] - boxes[:, 0]).clamp(min=0) * (boxes[:, 3] - boxes[:, 1]).clamp(min=0)
    top_left = torch.max(boxes[:, None, :2], boxes[None, :, :2])
    bottom_right = torch.min(boxes[:, None, 2:], boxes[None, :, 2:])
    intersection = (bottom_right - top_left).clamp(min=0).prod(dim=2)
    smaller = torch.min(areas[:, None], areas[None, :]).clamp(min=1e-6)
    nested = intersection / smaller >= overlap

    keep = torch.ones(len(boxes), dtype=torch.bool, device=boxes.device)
    for i in range(len(boxes)):
        if keep[i]:
            later = nested[i].clone()
            later[: i + 1] = False
            keep &= ~later
    return boxes[keep], scores[keep]


@torch.inference_mode()
def predict(model, images: list[torch.Tensor], tta: bool = True) -> list[dict]:
    """Predição com TTA opcional (espelhamento horizontal), devolvendo caixas xyxy e scores."""
    outputs = model(images)
    if not tta:
        return [
            dict(zip(("boxes", "scores"), suppress_nested(o["boxes"], o["scores"])))
            for o in outputs
        ]

    flipped_outputs = model([image.flip(-1) for image in images])
    results = []
    for image, original, flipped in zip(images, outputs, flipped_outputs):
        width = image.shape[-1]
        boxes = flipped["boxes"].clone()
        boxes[:, [0, 2]] = width - flipped["boxes"][:, [2, 0]]
        boxes, scores = _merge_tta(original, {"boxes": boxes, "scores": flipped["scores"]})
        if len(boxes):
            keep = nms(boxes, scores, iou_threshold=0.5)
            boxes, scores = suppress_nested(boxes[keep], scores[keep])
        results.append({"boxes": boxes, "scores": scores})
    return results


def predict_paths(model, paths: list[Path], device, batch_size: int = 16, num_workers: int = 0, tta: bool = True) -> list[dict]:
    """Prediz uma lista de imagens e devolve as predições na CPU, na mesma ordem."""
    loader = torch.utils.data.DataLoader(
        ImageFolderDataset(paths),
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=collate,
    )
    model.eval()
    results = [None] * len(paths)
    for images, indices in loader:
        images = [image.to(device, non_blocking=True) for image in images]
        # Precisão mista: mais rápido e cabe na VRAM junto com o estado do treino
        with torch.autocast(device.type, enabled=device.type == "cuda"):
            outputs = predict(model, images, tta=tta)
        for index, output in zip(indices, outputs):
            results[index] = {"boxes": output["boxes"].float().cpu(), "scores": output["scores"].float().cpu()}
    return results


def pseudo_label_status(prediction: dict, accept_threshold: float, negative_threshold: float) -> str:
    """Classifica a predição de uma imagem sem rótulo.

    - "aceito": todas as caixas relevantes têm score >= accept_threshold;
    - "negativo": nenhuma caixa passa de negative_threshold (imagem sem medidor);
    - "revisar": existe caixa na zona de incerteza; a imagem fica fora do treino
      porque tratar essa caixa como fundo ou como medidor ensinaria erro.
    """
    scores = prediction["scores"]
    if len(scores) == 0 or scores.max() < negative_threshold:
        return "negativo"
    uncertain = (scores >= negative_threshold) & (scores < accept_threshold)
    return "revisar" if uncertain.any() else "aceito"
