"""Train the meter detector using COCO bounding-box annotations."""

import argparse
import json
import logging
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Subset

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.dataset import MeterDataset
from models.model import MeterNetwork


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def detection_loss(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Compute objectness plus box regression loss for the grid detector."""
    pred_box = torch.sigmoid(prediction[:, :4])
    pred_objectness = prediction[:, 4]
    target_box = target[:, :4]
    target_objectness = target[:, 4]

    positive = target_objectness > 0.5
    objectness_loss = nn.functional.binary_cross_entropy_with_logits(
        pred_objectness,
        target_objectness,
        reduction="none",
    )
    objectness_weights = torch.where(
        positive,
        torch.full_like(objectness_loss, 10.0),
        torch.full_like(objectness_loss, 0.01),
    )
    objectness_loss = (objectness_loss * objectness_weights).sum() / objectness_weights.sum()

    if positive.any():
        box_loss = nn.functional.smooth_l1_loss(
            pred_box.permute(0, 2, 3, 1)[positive],
            target_box.permute(0, 2, 3, 1)[positive],
        )
    else:
        box_loss = prediction.sum() * 0.0

    return objectness_loss + 5.0 * box_loss


def run_epoch(model, loader, optimizer, device, training: bool) -> float:
    model.train(training)
    total_loss = 0.0
    batches = 0

    for images, targets in loader:
        images = images.to(device)
        targets = targets.to(device)

        with torch.set_grad_enabled(training):
            predictions = model(images)
            loss = detection_loss(predictions, targets)

            if training:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()

        total_loss += loss.item()
        batches += 1

    return total_loss / max(batches, 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/detector.json"))
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path("data/annotations/PSP_EXTRATLEITIMPL_030726_0121_instances.json"),
    )
    parser.add_argument(
        "--images",
        type=Path,
        default=Path("data/preprocessed_images/PSP_EXTRATLEITIMPL_030726_0121_preprocessed"),
    )
    parser.add_argument("--output", type=Path, default=Path("models/checkpoints/meter_detector.pt"))
    parser.add_argument("--log-file", type=Path, default=Path("logs/training.log"))
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--validation-ratio", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--num-workers", type=int)
    parser.add_argument("--resume", action="store_true", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = {}
    if args.config.is_file():
        with args.config.open(encoding="utf-8") as config_file:
            config = json.load(config_file).get("training", {})

    args.epochs = args.epochs if args.epochs is not None else config.get("epochs", 30)
    args.batch_size = args.batch_size if args.batch_size is not None else config.get("batch_size", 16)
    args.learning_rate = args.learning_rate if args.learning_rate is not None else config.get("learning_rate", 1e-3)
    args.validation_ratio = args.validation_ratio if args.validation_ratio is not None else config.get("validation_ratio", 0.2)
    args.seed = args.seed if args.seed is not None else config.get("seed", 42)
    args.num_workers = args.num_workers if args.num_workers is not None else config.get("num_workers", 0)
    args.resume = args.resume if args.resume is not None else config.get("resume", False)
    set_seed(args.seed)

    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(args.log_file, encoding="utf-8"),
        ],
    )
    logger = logging.getLogger(__name__)

    if not args.annotations.is_file():
        raise FileNotFoundError(f"Annotation file not found: {args.annotations}")
    if not args.images.is_dir():
        raise FileNotFoundError(f"Image directory not found: {args.images}")
    if not 0 < args.validation_ratio < 1:
        raise ValueError("--validation-ratio must be between 0 and 1")

    dataset = MeterDataset(args.annotations, args.images)
    indices = list(range(len(dataset)))
    random.Random(args.seed).shuffle(indices)
    validation_size = max(1, int(len(indices) * args.validation_ratio))
    validation_indices = indices[:validation_size]
    training_indices = indices[validation_size:]

    train_loader = DataLoader(
        Subset(dataset, training_indices),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    validation_loader = DataLoader(
        Subset(dataset, validation_indices),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MeterNetwork().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    best_validation_loss = float("inf")
    start_epoch = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.resume and args.output.is_file():
        checkpoint = torch.load(args.output, map_location=device, weights_only=True)
        model.load_state_dict(checkpoint["model_state_dict"])
        if "optimizer_state_dict" in checkpoint:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        start_epoch = checkpoint.get("epoch", 0) + 1
        best_validation_loss = checkpoint.get("validation_loss", best_validation_loss)
        logger.info("Resuming from epoch %03d", start_epoch)

    logger.info("Device: %s", device)
    logger.info(
        "Images: %d | train: %d | validation: %d",
        len(dataset),
        len(training_indices),
        len(validation_indices),
    )

    for epoch in range(start_epoch, args.epochs + 1):
        train_loss = run_epoch(model, train_loader, optimizer, device, training=True)
        validation_loss = run_epoch(model, validation_loader, optimizer, device, training=False)
        logger.info(
            "Epoch %03d/%03d | train_loss=%.5f | validation_loss=%.5f",
            epoch,
            args.epochs,
            train_loss,
            validation_loss,
        )

        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "epoch": epoch,
                    "grid_size": (dataset.grid_h, dataset.grid_w),
                    "class_names": ["Medidor"],
                    "validation_loss": validation_loss,
                },
                args.output,
            )
            logger.info("Saved checkpoint: %s", args.output)


if __name__ == "__main__":
    main()