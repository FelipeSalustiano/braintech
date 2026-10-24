"""Treino semi-supervisionado (professor-aluno com pseudo-rótulos) do detector de medidores.

Rodada 0: o professor (Faster R-CNN pré-treinado no COCO) é ajustado só com as
imagens rotuladas. Em cada rodada seguinte ele pseudo-rotula as imagens sem
rótulo (com TTA), e um aluno novo é treinado com rótulos reais + pseudo-rótulos
confiáveis e augmentação forte. O aluno só vira professor se melhorar no
conjunto de validação, que é sempre rotulado por humanos e nunca pseudo-rotulado.
"""

import argparse
import json
import logging
import math
import random
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, WeightedRandomSampler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.detector import (
    DetectionDataset,
    build_detector,
    collate,
    list_images,
    load_coco_samples,
    predict_paths,
    pseudo_label_status,
    train_transform,
)
from utils.detection_metrics import evaluate

DEFAULTS = {
    "annotations": "data/annotations/PSP_EXTRATLEITIMPL_030726_0121_instances.json",
    "labeled_images": "data/preprocessed_images/PSP_EXTRATLEITIMPL_030726_0121_preprocessed",
    "unlabeled_images": [],
    "output_dir": "models/checkpoints/semi_supervised",
    "rounds": 2,
    "teacher_epochs": 15,
    "student_epochs": 12,
    "batch_size": 8,
    "learning_rate": 0.01,
    "accept_threshold": 0.8,
    "negative_threshold": 0.05,
    "labeled_fraction": 0.5,
    "validation_ratio": 0.2,
    "seed": 42,
    "num_workers": 4,
}

logger = logging.getLogger(__name__)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def split_labeled(samples: list[dict], validation_ratio: float, seed: int) -> tuple[list[dict], list[dict]]:
    """Separa treino/validação.

    As imagens com caixa usam a mesma divisão de pipelines/train_detector.py
    (mesma ordem, seed e proporção), para comparar com o detector antigo.
    As negativas são divididas à parte, na mesma proporção.
    """
    positives = [s for s in samples if len(s["boxes"])]
    negatives = [s for s in samples if not len(s["boxes"])]
    validation, training = [], []
    for group in (positives, negatives):
        indices = list(range(len(group)))
        random.Random(seed).shuffle(indices)
        validation_size = max(1, int(len(indices) * validation_ratio))
        validation += [group[i] for i in indices[:validation_size]]
        training += [group[i] for i in indices[validation_size:]]
    return training, validation


def train_model(
    training_samples: list[dict],
    validation_samples: list[dict],
    sample_weights: list[float] | None,
    epochs: int,
    settings: dict,
    device,
    checkpoint_path: Path,
    tag: str,
) -> dict:
    """Treina um detector novo e salva o melhor checkpoint pelo AP50:95 de validação."""
    model = build_detector(pretrained=True).to(device)

    dataset = DetectionDataset(training_samples, transform=train_transform())
    if sample_weights is None:
        sampler = None
        steps_per_epoch = math.ceil(len(dataset) / settings["batch_size"])
    else:
        # Uma época = ver as imagens rotuladas uma vez, em média, junto dos pseudo-rótulos
        labeled = sum(1 for s in training_samples if not s.get("pseudo"))
        num_samples = int(labeled / settings["labeled_fraction"])
        sampler = WeightedRandomSampler(sample_weights, num_samples=num_samples, replacement=True)
        steps_per_epoch = math.ceil(num_samples / settings["batch_size"])

    loader = DataLoader(
        dataset,
        batch_size=settings["batch_size"],
        shuffle=sampler is None,
        sampler=sampler,
        num_workers=settings["num_workers"],
        collate_fn=collate,
        pin_memory=True,
        persistent_workers=settings["num_workers"] > 0,
        drop_last=True,
    )

    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.SGD(params, lr=settings["learning_rate"], momentum=0.9, weight_decay=1e-4)
    total_steps = epochs * steps_per_epoch
    warmup_steps = min(500, steps_per_epoch)
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lambda step: (step + 1) / warmup_steps if step < warmup_steps
        else 0.5 * (1 + math.cos(math.pi * (step - warmup_steps) / max(1, total_steps - warmup_steps))),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")

    validation_paths = [s["path"] for s in validation_samples]
    validation_boxes = [s["boxes"] for s in validation_samples]
    best = {"ap50_95": -1.0}

    for epoch in range(1, epochs + 1):
        model.train()
        started = time.time()
        running_loss = 0.0
        for images, targets in loader:
            images = [image.to(device, non_blocking=True) for image in images]
            targets = [{k: v.to(device, non_blocking=True) for k, v in t.items()} for t in targets]
            with torch.autocast(device.type, enabled=device.type == "cuda"):
                loss = sum(model(images, targets).values())
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            running_loss += loss.item()

        # Libera o cache do treino antes da inferência para não estourar a VRAM
        torch.cuda.empty_cache()
        predictions = predict_paths(
            model, validation_paths, device,
            batch_size=settings["batch_size"] * 2, num_workers=settings["num_workers"], tta=False,
        )
        metrics = evaluate(predictions, validation_boxes, settings["accept_threshold"])
        logger.info(
            "[%s] Epoch %03d/%03d | loss=%.4f | AP50=%.4f | AP50:95=%.4f | IoU=%.4f | %.0fs",
            tag, epoch, epochs, running_loss / len(loader),
            metrics["ap50"], metrics["ap50_95"], metrics["mean_iou_top1"], time.time() - started,
        )

        if metrics["ap50_95"] > best["ap50_95"]:
            best = {**metrics, "epoch": epoch}
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "epoch": epoch,
                    "class_names": ["Medidor"],
                    "architecture": "fasterrcnn_resnet50_fpn_v2",
                    "metrics": metrics,
                },
                checkpoint_path,
            )

    # Métricas finais do melhor checkpoint, já com TTA (é como os pseudo-rótulos são gerados)
    model.load_state_dict(torch.load(checkpoint_path, map_location=device, weights_only=True)["model_state_dict"])
    predictions = predict_paths(
        model, validation_paths, device,
        batch_size=settings["batch_size"] * 2, num_workers=settings["num_workers"], tta=True,
    )
    best_tta = evaluate(predictions, validation_boxes, settings["accept_threshold"])
    logger.info("[%s] Best epoch %03d with TTA: %s", tag, best["epoch"], json.dumps(best_tta))
    return {"model": model, "metrics": best_tta, "epoch": best["epoch"]}


def generate_pseudo_labels(model, unlabeled_paths: list[Path], settings: dict, device) -> tuple[list[dict], dict]:
    predictions = predict_paths(
        model, unlabeled_paths, device,
        batch_size=settings["batch_size"] * 2, num_workers=settings["num_workers"], tta=True,
    )
    samples = []
    counts = {"aceito": 0, "negativo": 0, "revisar": 0}
    for path, prediction in zip(unlabeled_paths, predictions):
        status = pseudo_label_status(prediction, settings["accept_threshold"], settings["negative_threshold"])
        counts[status] += 1
        if status == "revisar":
            continue
        keep = prediction["scores"] >= settings["accept_threshold"]
        samples.append({"path": path, "boxes": prediction["boxes"][keep].numpy(), "pseudo": True})
    return samples, counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/detector.json"))
    parser.add_argument("--log-file", type=Path, default=Path("logs/semi_supervised.log"))
    parser.add_argument("--rounds", type=int)
    parser.add_argument("--teacher-epochs", type=int)
    parser.add_argument("--student-epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--num-workers", type=int)
    parser.add_argument("--unlabeled-limit", type=int, help="Usa só N imagens sem rótulo (teste rápido)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = dict(DEFAULTS)
    if args.config.is_file():
        with args.config.open(encoding="utf-8") as config_file:
            settings.update(json.load(config_file).get("semi_supervised", {}))
    for key in ("rounds", "teacher_epochs", "student_epochs", "batch_size", "num_workers"):
        if getattr(args, key) is not None:
            settings[key] = getattr(args, key)

    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(args.log_file, encoding="utf-8")],
    )
    set_seed(settings["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_dir = Path(settings["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    labeled = load_coco_samples(Path(settings["annotations"]), Path(settings["labeled_images"]))
    training, validation = split_labeled(labeled, settings["validation_ratio"], settings["seed"])
    unlabeled_paths = [path for folder in settings["unlabeled_images"] for path in list_images(Path(folder))]
    if args.unlabeled_limit:
        unlabeled_paths = random.Random(settings["seed"]).sample(unlabeled_paths, args.unlabeled_limit)

    logger.info("Device: %s | settings: %s", device, json.dumps(settings))
    logger.info(
        "Labeled train: %d (%d negatives) | validation: %d (%d negatives) | unlabeled: %d",
        len(training), sum(not len(s["boxes"]) for s in training),
        len(validation), sum(not len(s["boxes"]) for s in validation),
        len(unlabeled_paths),
    )

    history = []
    teacher = train_model(
        training, validation, None, settings["teacher_epochs"], settings, device,
        output_dir / "round_0.pt", "round 0 / teacher",
    )
    history.append({"round": 0, "epoch": teacher["epoch"], "metrics": teacher["metrics"]})
    best_round = 0

    for round_index in range(1, settings["rounds"] + 1):
        pseudo_samples, counts = generate_pseudo_labels(teacher["model"], unlabeled_paths, settings, device)
        logger.info("[round %d] Pseudo-labels: %s", round_index, json.dumps(counts))
        del teacher["model"]
        torch.cuda.empty_cache()

        samples = training + pseudo_samples
        labeled_weight = settings["labeled_fraction"] / len(training)
        pseudo_weight = (1 - settings["labeled_fraction"]) / max(1, len(pseudo_samples))
        weights = [pseudo_weight if s.get("pseudo") else labeled_weight for s in samples]

        student = train_model(
            samples, validation, weights, settings["student_epochs"], settings, device,
            output_dir / f"round_{round_index}.pt", f"round {round_index} / student",
        )
        history.append({
            "round": round_index, "epoch": student["epoch"],
            "metrics": student["metrics"], "pseudo_labels": counts,
        })

        if student["metrics"]["ap50_95"] <= teacher["metrics"]["ap50_95"]:
            logger.info("[round %d] Student did not beat the teacher; stopping.", round_index)
            break
        teacher = student
        best_round = round_index

    shutil.copyfile(output_dir / f"round_{best_round}.pt", output_dir / "best.pt")
    summary = {"best_round": best_round, "settings": settings, "history": history}
    with (output_dir / "summary.json").open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2, default=str)
    logger.info("Best round: %d -> %s", best_round, output_dir / "best.pt")


if __name__ == "__main__":
    main()
