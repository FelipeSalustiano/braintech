"""Rotula as imagens sem anotação com o melhor detector semi-supervisionado.

Para cada pasta gera, em `pseudo_labels_dir`:
- <pasta>_instances.json: COCO no mesmo formato do CVAT. Imagens "aceito" trazem
  as caixas confiáveis; imagens "revisar" trazem as caixas incertas para um
  humano corrigir; imagens "negativo" ficam sem anotação.
- <pasta>_status.csv: status, maior score e número de caixas por imagem.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import torch
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.detector import CLASS_NAMES, list_images, load_detector, predict_paths, pseudo_label_status
from pipelines.train_semi_supervised import DEFAULTS

STATUS_COLORS = {"aceito": "lime", "revisar": "orange"}


def dataset_name(folder: Path) -> str:
    return folder.name.removesuffix("_preprocessed")


def build_coco(paths: list[Path], predictions: list[dict], statuses: list[str], settings: dict) -> dict:
    images, annotations = [], []
    for image_id, (path, prediction, status) in enumerate(zip(paths, predictions, statuses), start=1):
        width, height = Image.open(path).size
        images.append({
            "id": image_id, "width": width, "height": height, "file_name": path.name,
            "license": 0, "flickr_url": "", "coco_url": "", "date_captured": 0,
        })
        if status == "negativo":
            continue

        threshold = settings["accept_threshold"] if status == "aceito" else settings["negative_threshold"]
        for box, score in zip(prediction["boxes"], prediction["scores"]):
            if score < threshold:
                continue
            x1, y1, x2, y2 = (round(float(v), 2) for v in box)
            annotations.append({
                "id": len(annotations) + 1,
                "image_id": image_id,
                "category_id": 1,
                "segmentation": [],
                "area": round((x2 - x1) * (y2 - y1), 4),
                "bbox": [x1, y1, round(x2 - x1, 2), round(y2 - y1, 2)],
                "iscrowd": 0,
                "attributes": {"occluded": False, "rotation": 0.0},
                "score": round(float(score), 4),
                "pseudo_label_status": status,
            })

    return {
        "licenses": [{"name": "", "id": 0, "url": ""}],
        "info": {"description": "Pseudo-rótulos do detector semi-supervisionado", "version": "", "year": ""},
        "categories": [{"id": i + 1, "name": name, "supercategory": ""} for i, name in enumerate(CLASS_NAMES)],
        "images": images,
        "annotations": annotations,
    }


def save_preview(path: Path, prediction: dict, status: str, settings: dict, output: Path) -> None:
    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    threshold = settings["accept_threshold"] if status == "aceito" else settings["negative_threshold"]
    for box, score in zip(prediction["boxes"], prediction["scores"]):
        if score >= threshold:
            draw.rectangle(box.tolist(), outline=STATUS_COLORS[status], width=3)
            draw.text((box[0] + 4, box[1] + 4), f"{score:.2f}", fill=STATUS_COLORS[status])
    draw.text((4, 4), status, fill="red")
    output.mkdir(parents=True, exist_ok=True)
    image.save(output / path.name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/detector.json"))
    parser.add_argument("--checkpoint", type=Path, help="Padrão: <output_dir>/best.pt")
    parser.add_argument("--folders", type=Path, nargs="+", help="Padrão: unlabeled_images do config")
    parser.add_argument("--output", type=Path, help="Padrão: pseudo_labels_dir do config")
    parser.add_argument("--accept-threshold", type=float)
    parser.add_argument("--preview-dir", type=Path, help="Salva as imagens com as caixas desenhadas")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = dict(DEFAULTS, pseudo_labels_dir="data/annotations/pseudo")
    if args.config.is_file():
        with args.config.open(encoding="utf-8") as config_file:
            settings.update(json.load(config_file).get("semi_supervised", {}))
    if args.accept_threshold is not None:
        settings["accept_threshold"] = args.accept_threshold

    checkpoint = args.checkpoint or Path(settings["output_dir"]) / "best.pt"
    folders = args.folders or [Path(folder) for folder in settings["unlabeled_images"]]
    output = args.output or Path(settings["pseudo_labels_dir"])
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")
    output.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_detector(checkpoint, device)

    for folder in folders:
        paths = list_images(folder)
        predictions = predict_paths(
            model, paths, device,
            batch_size=settings["batch_size"] * 2, num_workers=settings["num_workers"], tta=True,
        )
        statuses = [
            pseudo_label_status(p, settings["accept_threshold"], settings["negative_threshold"])
            for p in predictions
        ]

        name = dataset_name(folder)
        with (output / f"{name}_instances.json").open("w", encoding="utf-8") as json_file:
            json.dump(build_coco(paths, predictions, statuses, settings), json_file, ensure_ascii=False)

        with (output / f"{name}_status.csv").open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["file_name", "status", "max_score", "boxes"])
            for path, prediction, status in zip(paths, predictions, statuses):
                scores = prediction["scores"]
                writer.writerow([
                    path.name, status,
                    f"{float(scores.max()):.4f}" if len(scores) else "0",
                    int((scores >= settings["negative_threshold"]).sum()),
                ])

        if args.preview_dir:
            for path, prediction, status in zip(paths, predictions, statuses):
                save_preview(path, prediction, status, settings, args.preview_dir / name / status)

        counts = {status: statuses.count(status) for status in ("aceito", "revisar", "negativo")}
        print(f"{name}: {len(paths)} images | {counts} | {output / f'{name}_instances.json'}")


if __name__ == "__main__":
    main()
