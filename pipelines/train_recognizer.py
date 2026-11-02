"""Treina o reconhecedor da leitura com os recortes de display e as leituras dos CSVs.

Entrada: uma pasta por lote em `crops_root` (saída do crop_detector.py rodado
com o detector de display, com manifest.csv) e os CSVs dos leituristas.
Saída, em `output_dir`: best.pt, split.csv (treino/validação/teste por foto),
test_predictions.csv e summary.json.

As leituras dos CSVs são digitadas pelo leiturista, então há algum ruído de
rótulo; a acurácia de teste é um limite inferior da acurácia real.

As fotos de treino conferidas à mão (data/review/review_train_*.csv, exportados
pelas páginas do utils/build_review_page.py) trocam a leitura do CSV pela
conferida. As marcadas como ilegíveis não ensinam dígitos: ensinam a saída de
legibilidade, que só aprende com fotos conferidas.
"""

import argparse
import csv
import json
import logging
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.recognizer import NUM_DIGITS, DisplayDataset, MeterReader, collate, decode, load_display, train_transform
from pipelines.evaluate_ocr import load_ground_truth, photo_key
from src.meter_reading import same_reading

DEFAULTS = {
    "crops_root": "data/display_crops",
    "sheets": "data/sheets",
    "output_dir": "models/checkpoints/recognizer",
    "epochs": 40,
    "batch_size": 64,
    "learning_rate": 0.001,
    "validation_ratio": 0.1,
    "test_ratio": 0.1,
    "seed": 42,
    # Recortes do detector com score abaixo disso ficam fora do treino (caixa duvidosa)
    "min_detection_score": 0.5,
    # CSVs exportados das páginas de conferência das fotos de treino
    "reviews": "data/review/review_train_*.csv",
    # Quantas vezes cada foto conferida entra por época: rótulo limpo vale mais que o do CSV
    "review_repeat": 3,
    # Limpeza de rótulos por validação cruzada (0 desliga): ver label_scores().
    # Testada com 4 folds e limiar 0,2: piorou (63,5% -> 59,4% nas fotos
    # legíveis conferidas à mão) porque o modelo deixa de ver displays
    # ilegíveis no treino e passa a dar confiança alta para eles.
    "clean_folds": 0,
    "clean_epochs": 25,
    "clean_min_label_prob": 0.2,
}
CONFIDENCE_LEVELS = [0.0, 0.5, 0.7, 0.9, 0.95]

logger = logging.getLogger(__name__)


def load_samples(crops_root: Path, sheets: Path, min_score: float) -> list[dict]:
    """Uma amostra por foto que tem recorte de display e leitura no CSV."""
    truth = load_ground_truth(sheets, keep_zeros=False)
    expected_by_photo = dict(zip(truth["stem"], truth["expected"]))

    samples = []
    for manifest_path in sorted(crops_root.glob("*/manifest.csv")):
        with manifest_path.open(encoding="utf-8") as manifest_file:
            for row in csv.DictReader(manifest_file):
                key = photo_key(row["image"])
                if not row["crop_path"] or key not in expected_by_photo:
                    continue
                if float(row["score"] or 0) < min_score:
                    continue
                samples.append({
                    "image": row["image"],
                    "lot": manifest_path.parent.name,
                    "crop_path": Path(row["crop_path"]),
                    "label": str(int(expected_by_photo[key])),
                })
    return samples


def load_reviews(pattern: str) -> dict[str, str | None]:
    """Leitura conferida por foto; None quando marcada como ilegível."""
    reviews = {}
    for path in sorted(Path().glob(pattern)):
        with path.open(encoding="utf-8") as review_file:
            for row in csv.DictReader(review_file):
                if row["illegible"] == "1":
                    reviews[row["image"]] = None
                elif row["human_reading"]:
                    reading = str(int(row["human_reading"]))
                    if len(reading) > NUM_DIGITS:
                        # Erro de digitação na conferência: a foto fica com o rótulo do CSV
                        logger.warning("Ignoring review of %s in %s: %r has more than %d digits", row["image"], path.name, row["human_reading"], NUM_DIGITS)
                        continue
                    reviews[row["image"]] = reading
    return reviews


def apply_reviews(train: list[dict], reviews: dict[str, str | None], repeat: int) -> list[dict]:
    """Troca o rótulo do CSV pelo conferido e repete as fotos conferidas `repeat` vezes."""
    result = []
    for sample in train:
        if sample["image"] not in reviews:
            result.append({**sample, "illegible": math.nan})
            continue
        reading = reviews[sample["image"]]
        reviewed = {**sample, "label": reading or "", "illegible": 0.0 if reading else 1.0}
        result += [reviewed] * repeat
    return result


def split_samples(samples: list[dict], validation_ratio: float, test_ratio: float, seed: int) -> dict[str, list[dict]]:
    indices = list(range(len(samples)))
    random.Random(seed).shuffle(indices)
    test_size = int(len(indices) * test_ratio)
    validation_size = int(len(indices) * validation_ratio)
    return {
        "test": [samples[i] for i in indices[:test_size]],
        "validation": [samples[i] for i in indices[test_size:test_size + validation_size]],
        "train": [samples[i] for i in indices[test_size + validation_size:]],
    }


@torch.inference_mode()
def predict(model, loader, device) -> tuple[list[tuple[str, float]], list[float]]:
    """Leitura e confiança de cada recorte, e a probabilidade de estar ilegível."""
    model.eval()
    results, illegible = [], []
    for images, _, _, _ in loader:
        with torch.autocast(device.type, enabled=device.type == "cuda"):
            logits, illegible_logits = model(images.to(device, non_blocking=True))
        results += decode(logits.float().cpu())
        illegible += illegible_logits.float().sigmoid().cpu().tolist()
    return results, illegible


def accuracy_report(predictions: list[tuple[str, float]], labels: list[str]) -> dict:
    """Acurácia e cobertura por limiar de confiança: o que dá para aceitar automaticamente."""
    correct = np.array([same_reading(text, label) for (text, _), label in zip(predictions, labels)])
    confidence = np.array([score for _, score in predictions])
    report = {"accuracy": float(correct.mean()) if len(correct) else 0.0, "by_confidence": {}}
    for level in CONFIDENCE_LEVELS:
        accepted = confidence >= level
        report["by_confidence"][str(level)] = {
            "coverage": float(accepted.mean()) if len(accepted) else 0.0,
            "accuracy": float(correct[accepted].mean()) if accepted.any() else 0.0,
        }
    return report


def save_checkpoint(state: dict, path: Path, attempts: int = 5) -> None:
    """Grava num temporário e troca pelo definitivo.

    No Windows, o antivírus ou o indexador às vezes ainda está com o checkpoint
    anterior aberto e a gravação direta falha (erro 1224); a troca é repetida.
    """
    temporary = path.with_suffix(".tmp")
    torch.save(state, temporary)
    for attempt in range(attempts):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(1)


def fit(train_dataset, validation_dataset, epochs: int, settings: dict, device, checkpoint_path: Path, tag: str):
    """Treina um modelo novo e guarda o melhor checkpoint pela acurácia de validação."""
    train_loader = DataLoader(train_dataset, batch_size=settings["batch_size"], shuffle=True, collate_fn=collate, drop_last=True)
    validation_loader = DataLoader(validation_dataset, batch_size=256, collate_fn=collate)

    model = MeterReader().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=settings["learning_rate"], weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=settings["learning_rate"], total_steps=epochs * len(train_loader), pct_start=0.15,
    )
    criterion = nn.CrossEntropyLoss(reduction="none")
    legibility_criterion = nn.BCEWithLogitsLoss()
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    best_accuracy, best_epoch = -1.0, 0

    for epoch in range(1, epochs + 1):
        model.train()
        started, running_loss = time.time(), 0.0
        for images, targets, labels, illegible in train_loader:
            images, targets, illegible = (t.to(device, non_blocking=True) for t in (images, targets, illegible))
            with torch.autocast(device.type, enabled=device.type == "cuda"):
                logits, illegible_logits = model(images)
            # Foto ilegível não tem leitura: fica fora da perda dos dígitos
            has_reading = torch.tensor([bool(label) for label in labels], device=device)
            digit_loss = criterion(logits.float().reshape(-1, 10), targets.reshape(-1)).view(-1, NUM_DIGITS).mean(1)
            loss = digit_loss[has_reading].mean() if has_reading.any() else digit_loss.sum() * 0
            # Legibilidade só é conhecida nas fotos conferidas (as outras vêm NaN)
            known = ~torch.isnan(illegible)
            if known.any():
                loss = loss + legibility_criterion(illegible_logits.float()[known], illegible[known])
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            running_loss += loss.item()

        report = accuracy_report(predict(model, validation_loader, device)[0], validation_dataset.labels)
        logger.info(
            "[%s] Epoch %03d/%03d | loss=%.4f | val_acc=%.4f | %.0fs",
            tag, epoch, epochs, running_loss / len(train_loader), report["accuracy"], time.time() - started,
        )
        if report["accuracy"] > best_accuracy:
            best_accuracy, best_epoch = report["accuracy"], epoch
            save_checkpoint({"model_state_dict": model.state_dict(), "epoch": epoch, "architecture": "meter_reader_6_digits_legibility"}, checkpoint_path)

    model.load_state_dict(torch.load(checkpoint_path, map_location=device, weights_only=True)["model_state_dict"])
    return model, best_epoch


@torch.inference_mode()
def label_probability(model, dataset, device) -> list[float]:
    """Probabilidade que o modelo dá ao rótulo do CSV: a menor entre as 6 posições."""
    model.eval()
    loader = DataLoader(dataset, batch_size=256, collate_fn=collate)
    scores = []
    for images, targets, _, _ in loader:
        probabilities = model(images.to(device))[0].float().softmax(-1).cpu()
        label_probabilities = probabilities.gather(-1, targets[..., None]).squeeze(-1)  # (N, 6)
        scores += label_probabilities.min(-1).values.tolist()
    return scores


def label_scores(samples: list[dict], images: list, settings: dict, device, output_dir: Path) -> list[float]:
    """Nota de cada amostra de treino dada por um modelo que não a viu (validação cruzada).

    Metade das fotos é ilegível e cerca de 1/4 das legíveis tem a leitura do
    CSV diferente do display (conferência manual de 200 fotos do teste). Uma
    nota baixa indica uma das duas coisas; essas amostras saem do treino final.
    As notas ficam em label_scores.csv e são reaproveitadas se a lista de
    amostras não mudou, para testar outros limiares sem retreinar os folds.
    """
    scores_path = output_dir / "label_scores.csv"
    if scores_path.is_file():
        with scores_path.open(encoding="utf-8") as scores_file:
            saved = {row["image"]: float(row["label_prob"]) for row in csv.DictReader(scores_file)}
        if all(s["image"] in saved for s in samples):
            logger.info("Reusing %s", scores_path)
            return [saved[s["image"]] for s in samples]

    folds = settings["clean_folds"]
    order = list(range(len(samples)))
    random.Random(settings["seed"]).shuffle(order)
    scores = [0.0] * len(samples)
    for fold in range(folds):
        held_out = order[fold::folds]
        held_set = set(held_out)
        train_indices = [i for i in order if i not in held_set]
        train_dataset = DisplayDataset([images[i] for i in train_indices], [samples[i]["label"] for i in train_indices], transform=train_transform())
        held_dataset = DisplayDataset([images[i] for i in held_out], [samples[i]["label"] for i in held_out])
        # O fold avaliado faz papel de validação: o objetivo aqui é só pontuar, não escolher modelo
        model, _ = fit(train_dataset, held_dataset, settings["clean_epochs"], settings, device, output_dir / "fold.pt", f"fold {fold + 1}/{folds}")
        for index, score in zip(held_out, label_probability(model, held_dataset, device)):
            scores[index] = score
    (output_dir / "fold.pt").unlink(missing_ok=True)

    with scores_path.open("w", newline="", encoding="utf-8") as scores_file:
        writer = csv.writer(scores_file)
        writer.writerow(["image", "lot", "label", "label_prob"])
        writer.writerows([s["image"], s["lot"], s["label"], f"{score:.4f}"] for s, score in zip(samples, scores))
    return scores


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path("configs/detector.json"))
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--log-file", type=Path, default=Path("logs/recognizer.log"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = dict(DEFAULTS)
    if args.config.is_file():
        with args.config.open(encoding="utf-8") as config_file:
            settings.update(json.load(config_file).get("recognizer", {}))
    if args.epochs is not None:
        settings["epochs"] = args.epochs

    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(args.log_file, encoding="utf-8")],
    )
    random.seed(settings["seed"])
    torch.manual_seed(settings["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_dir = Path(settings["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = load_samples(Path(settings["crops_root"]), Path(settings["sheets"]), settings["min_detection_score"])
    if not samples:
        raise RuntimeError(f"No samples: run crop_detector.py with the display checkpoint into {settings['crops_root']}/<lote>")
    splits = split_samples(samples, settings["validation_ratio"], settings["test_ratio"], settings["seed"])
    with (output_dir / "split.csv").open("w", newline="", encoding="utf-8") as split_file:
        writer = csv.writer(split_file)
        writer.writerow(["image", "lot", "split", "label"])
        for name, group in splits.items():
            writer.writerows([s["image"], s["lot"], name, s["label"]] for s in group)
    logger.info("Device: %s | settings: %s", device, json.dumps(settings))
    logger.info("Samples: %s", {name: len(group) for name, group in splits.items()})

    # Só o treino usa a conferência: as fotos conferidas do teste medem o modelo (utils/score_review.py)
    reviews = load_reviews(settings["reviews"])
    reviewed_train = [s for s in splits["train"] if s["image"] in reviews]
    splits["train"] = apply_reviews(splits["train"], reviews, settings["review_repeat"])
    logger.info(
        "Reviewed training photos: %d (%d illegible), outside the training split: %d",
        len(reviewed_train), sum(reviews[s["image"]] is None for s in reviewed_train), len(reviews) - len(reviewed_train),
    )

    # Tudo em memória: ~11 mil recortes de 48 x 160 são ~80 MB e dispensam workers no Windows
    datasets = {
        name: DisplayDataset(
            [load_display(s["crop_path"]) for s in group],
            [s["label"] for s in group],
            transform=train_transform() if name == "train" else None,
            illegible=[s.get("illegible", math.nan) for s in group],
        )
        for name, group in splits.items()
    }
    eval_loaders = {
        name: DataLoader(datasets[name], batch_size=256, collate_fn=collate)
        for name in ("validation", "test")
    }

    if settings["clean_folds"] > 1:
        scores = label_scores(splits["train"], datasets["train"].images, settings, device, output_dir)
        keep = [score >= settings["clean_min_label_prob"] for score in scores]
        logger.info(
            "Label cleaning: kept %d of %d training samples (label prob >= %.2f)",
            sum(keep), len(keep), settings["clean_min_label_prob"],
        )
        datasets["train"] = DisplayDataset(
            [image for image, k in zip(datasets["train"].images, keep) if k],
            [label for label, k in zip(datasets["train"].labels, keep) if k],
            transform=train_transform(),
        )

    checkpoint_path = output_dir / "best.pt"
    model, best_epoch = fit(datasets["train"], datasets["validation"], settings["epochs"], settings, device, checkpoint_path, "final")
    validation_report = accuracy_report(predict(model, eval_loaders["validation"], device)[0], datasets["validation"].labels)
    test_predictions, test_illegible = predict(model, eval_loaders["test"], device)
    test_report = accuracy_report(test_predictions, datasets["test"].labels)

    with (output_dir / "test_predictions.csv").open("w", newline="", encoding="utf-8") as predictions_file:
        writer = csv.writer(predictions_file)
        writer.writerow(["image", "lot", "label", "reading", "confidence", "illegible_prob", "correct"])
        for sample, (text, score), illegible in zip(splits["test"], test_predictions, test_illegible):
            writer.writerow([sample["image"], sample["lot"], sample["label"], text, f"{score:.4f}", f"{illegible:.4f}", same_reading(text, sample["label"])])

    summary = {"best_epoch": best_epoch, "settings": settings, "validation": validation_report, "test": test_report}
    with (output_dir / "summary.json").open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2)
    logger.info("Best epoch %d | test: %s", best_epoch, json.dumps(test_report))


if __name__ == "__main__":
    main()
