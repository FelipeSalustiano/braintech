"""Run meter detection with a trained checkpoint."""

import argparse
import json
import sys
from pathlib import Path

import torch
from PIL import Image, ImageDraw
from torchvision import transforms

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.model import MeterNetwork

MODEL_IMAGE_SIZE = (360, 480)


def decode_best_box(prediction: torch.Tensor, threshold: float):
    """Decode the highest-confidence grid cell into pixel coordinates."""
    prediction = prediction[0]
    confidence = prediction[4].sigmoid()
    score, flat_index = confidence.reshape(-1).max(0)
    if score.item() < threshold:
        return None

    grid_h, grid_w = confidence.shape
    grid_y = int(flat_index.item() // grid_w)
    grid_x = int(flat_index.item() % grid_w)
    box = prediction[:4, grid_y, grid_x].sigmoid()
    center_x = (grid_x + box[0].item()) / grid_w
    center_y = (grid_y + box[1].item()) / grid_h
    width = box[2].item()
    height = box[3].item()
    return center_x, center_y, width, height, score.item()


def detect(model, image_path: Path, output_path: Path, device, threshold: float) -> bool:
    image = Image.open(image_path).convert("RGB")
    model_image = image.resize(MODEL_IMAGE_SIZE, Image.Resampling.BILINEAR)
    image_tensor = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.ToTensor(),
    ])(model_image).unsqueeze(0).to(device)

    with torch.inference_mode():
        prediction = model(image_tensor)
    decoded = decode_best_box(prediction, threshold)

    result = image.copy()
    if decoded is None:
        result.save(output_path)
        return False

    center_x, center_y, width, height, score = decoded
    image_width, image_height = image.size
    left = max(0, int((center_x - width / 2) * image_width))
    top = max(0, int((center_y - height / 2) * image_height))
    right = min(image_width - 1, int((center_x + width / 2) * image_width))
    bottom = min(image_height - 1, int((center_y + height / 2) * image_height))

    draw = ImageDraw.Draw(result)
    draw.rectangle((left, top, right, bottom), outline="red", width=3)
    draw.text((left, max(0, top - 16)), f"Medidor {score:.2f}", fill="red")
    result.save(output_path)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/detector.json"))
    parser.add_argument("--checkpoint", type=Path, help="Override checkpoint from config")
    parser.add_argument("--input", type=Path, help="Override input from config")
    parser.add_argument("--output", type=Path, help="Override output from config")
    parser.add_argument("--threshold", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = {}
    if args.config.is_file():
        with args.config.open(encoding="utf-8") as config_file:
            config = json.load(config_file)

    checkpoint_path = Path(args.checkpoint or config.get("checkpoint", "models/checkpoints/meter_detector.pt"))
    input_path = Path(args.input or config.get("input", "data/preprocessed_images/PSP_EXTRATLEITIMPL_210526_0335_preprocessed"))
    output_path = Path(args.output or config.get("output", "predictions"))

    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MeterNetwork().to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    threshold = args.threshold
    if threshold is None:
        threshold = config.get("threshold", 0.1)
    if threshold is None:
        threshold = 0.1

    images = [input_path] if input_path.is_file() else sorted(
        path for path in input_path.rglob("*")
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    )
    output_path.mkdir(parents=True, exist_ok=True)

    detected = 0
    for image_path in images:
        image_output_path = output_path / image_path.name
        if detect(model, image_path, image_output_path, device, threshold):
            detected += 1

    print(f"Processed: {len(images)} | detections: {detected} | output: {output_path}")


if __name__ == "__main__":
    main()