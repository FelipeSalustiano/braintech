"""Lê o valor do display de cada foto com o reconhecedor treinado.

Entrada: a pasta de recortes de display de um lote (saída do crop_detector.py
rodado com o detector de display, com manifest.csv).
Saída, em `output`: readings.csv, uma linha por foto do manifest, com a
leitura, a confiança e o status:
- lido: confiança >= accept_confidence, pode ser aceita automaticamente;
- leitura_suspeita: confiança baixa, vai para conferência humana;
- ilegivel: probabilidade de display ilegível >= max_illegible_prob;
- sem_leitura: o detector não achou display na foto.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.recognizer import load_display, load_recognizer, recognize
from src.meter_reading import STATUS_SEM_LEITURA, reading_status

DEFAULTS = {
    "input": "data/display_crops",
    "output": "data/readings",
    "checkpoint": "models/checkpoints/recognizer/best.pt",
    "accept_confidence": 0.9,
    "max_illegible_prob": 0.5,
}
READINGS_FIELDS = ["image", "crop_status", "detection_score", "status", "reading", "confidence", "illegible_prob"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path("configs/detector.json"))
    parser.add_argument("--input", type=Path, help="Pasta de recortes de display de um lote (com manifest.csv)")
    parser.add_argument("--output", type=Path, help="Pasta de saída das leituras")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--accept-confidence", type=float, help="Confiança mínima para o status 'lido'")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = {}
    if args.config.is_file():
        with args.config.open(encoding="utf-8") as config_file:
            config = json.load(config_file)
    settings = {**DEFAULTS, **config.get("reading", {})}

    input_path = Path(args.input or settings["input"])
    output_path = Path(args.output or settings["output"])
    checkpoint_path = Path(args.checkpoint or settings["checkpoint"])
    accept_confidence = args.accept_confidence if args.accept_confidence is not None else settings["accept_confidence"]
    manifest_path = input_path / "manifest.csv"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path} (rode pipelines/crop_detector.py com o detector de display antes)")
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    with manifest_path.open(encoding="utf-8") as manifest_file:
        manifest = list(csv.DictReader(manifest_file))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_recognizer(checkpoint_path, device)
    cropped = [row for row in manifest if row["crop_path"]]
    predictions = recognize(model, [load_display(Path(row["crop_path"])) for row in cropped], device)
    prediction_by_image = {row["image"]: prediction for row, prediction in zip(cropped, predictions)}

    rows = []
    for row in manifest:
        output = {"image": row["image"], "crop_status": row["status"], "detection_score": row["score"]}
        if row["image"] not in prediction_by_image:
            output["status"] = STATUS_SEM_LEITURA
        else:
            reading, confidence, illegible_prob = prediction_by_image[row["image"]]
            output.update({
                "status": reading_status(reading, confidence, accept_confidence, illegible_prob, settings["max_illegible_prob"]),
                "reading": reading,
                "confidence": f"{confidence:.4f}",
                "illegible_prob": f"{illegible_prob:.4f}",
            })
        rows.append(output)

    output_path.mkdir(parents=True, exist_ok=True)
    readings_path = output_path / "readings.csv"
    with readings_path.open("w", newline="", encoding="utf-8") as readings_file:
        writer = csv.DictWriter(readings_file, fieldnames=READINGS_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    summary = " | ".join(f"{status}: {count}" for status, count in sorted(counts.items()))
    print(f"Processed: {len(rows)} | {summary} | readings: {readings_path}")


if __name__ == "__main__":
    main()
