"""Detect the meter in each image and save the cropped region for the OCR stage."""

import argparse
import csv
import json
import sys
from pathlib import Path

import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.detector import list_images, load_detector, predict_paths
from src.meter_cropping import (
    STATUS_SEM_DETECCAO,
    CropResult,
    compute_crop_box,
    crop_image,
)

DEFAULT_CHECKPOINT = "models/checkpoints/semi_supervised/best.pt"
MANIFEST_FIELDS = [
    "image",
    "status",
    "score",
    "left",
    "top",
    "right",
    "bottom",
    "outside_ratio",
    "crop_path",
]


def best_box(prediction: dict, image_size: tuple[int, int], threshold: float):
    """Return the highest-score box as (center_x, center_y, width, height, score), normalized to 0-1."""
    scores = prediction["scores"]
    if len(scores) == 0 or float(scores.max()) < threshold:
        return None
    index = int(scores.argmax())
    x1, y1, x2, y2 = (float(v) for v in prediction["boxes"][index])
    image_width, image_height = image_size
    return (
        (x1 + x2) / 2 / image_width,
        (y1 + y2) / 2 / image_height,
        (x2 - x1) / image_width,
        (y2 - y1) / image_height,
        float(scores[index]),
    )


def crop_from_prediction(image_path: Path, prediction: dict, crop_source: Path | None, output_dir: Path, settings: dict) -> dict:
    """Crop the meter from one image using its prediction and return a manifest row."""
    image = Image.open(image_path).convert("RGB")
    decoded = best_box(prediction, image.size, settings["threshold"])

    row = {"image": image_path.name, "crop_path": ""}
    if decoded is None:
        best_score = float(prediction["scores"].max()) if len(prediction["scores"]) else None
        result = CropResult(status=STATUS_SEM_DETECCAO, score=best_score)
    else:
        # The box is normalized (0 to 1), so it can be applied to the detector
        # input or to another version of the same photo (for example, the
        # original color image before preprocessing).
        if crop_source is not None:
            source_path = crop_source / image_path.name
            if not source_path.is_file():
                raise FileNotFoundError(f"Crop source not found: {source_path}")
            image = Image.open(source_path).convert("RGB")

        center_x, center_y, width, height, score = decoded
        result = compute_crop_box(
            center_x,
            center_y,
            width,
            height,
            score,
            image.size,
            margin=settings["margin"],
            min_size=settings["min_size"],
            max_outside_ratio=settings["max_outside_ratio"],
        )
        if result.left is not None:
            crop_path = output_dir / f"{image_path.stem}.png"
            crop_image(image, result).save(crop_path)
            row["crop_path"] = str(crop_path)

    row.update({
        "status": result.status,
        "score": "" if result.score is None else f"{result.score:.4f}",
        "left": result.left,
        "top": result.top,
        "right": result.right,
        "bottom": result.bottom,
        "outside_ratio": f"{result.outside_ratio:.4f}",
    })
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/detector.json"))
    parser.add_argument("--checkpoint", type=Path, help="Override cropping checkpoint from config")
    parser.add_argument("--input", type=Path, help="Override cropping input from config")
    parser.add_argument("--output", type=Path, help="Override cropping output from config")
    parser.add_argument("--crop-source", type=Path, help="Folder with the images to crop (same file names as input)")
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--margin", type=float)
    parser.add_argument("--no-tta", action="store_true", help="Disable the horizontal-flip test-time augmentation")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = {}
    if args.config.is_file():
        with args.config.open(encoding="utf-8") as config_file:
            config = json.load(config_file)
    cropping = config.get("cropping", {})

    checkpoint_path = Path(args.checkpoint or cropping.get("checkpoint", DEFAULT_CHECKPOINT))
    input_path = Path(args.input or cropping.get("input", config.get("input", "data/imgs_preprocessed_test")))
    output_path = Path(args.output or cropping.get("output", "data/crops"))
    crop_source = args.crop_source or cropping.get("crop_source")
    crop_source = Path(crop_source) if crop_source else None

    settings = {
        "threshold": args.threshold if args.threshold is not None else cropping.get("threshold", 0.8),
        "margin": args.margin if args.margin is not None else cropping.get("margin", 0.10),
        "min_size": cropping.get("min_size", 32),
        "max_outside_ratio": cropping.get("max_outside_ratio", 0.15),
    }

    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_detector(checkpoint_path, device)

    images = [input_path] if input_path.is_file() else list_images(input_path)
    output_path.mkdir(parents=True, exist_ok=True)

    predictions = predict_paths(model, images, device, batch_size=4, tta=not args.no_tta)
    rows = [
        crop_from_prediction(image_path, prediction, crop_source, output_path, settings)
        for image_path, prediction in zip(images, predictions)
    ]

    # The manifest is the hand-off to the OCR stage: one row per image.
    manifest_path = output_path / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    summary = " | ".join(f"{status}: {count}" for status, count in sorted(counts.items()))
    print(f"Processed: {len(images)} | {summary} | manifest: {manifest_path}")


if __name__ == "__main__":
    main()
