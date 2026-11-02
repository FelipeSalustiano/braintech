"""
Compara a conferência manual (review.csv exportado da página) com o modelo e com o CSV dos leituristas.

Uso, na raiz do projeto:
    python utils/score_review.py --review data/review/review.csv

Mostra, nas fotos legíveis: acerto do modelo contra a leitura conferida,
acerto do CSV contra a leitura conferida (o ruído do gabarito) e o acerto do
modelo por limiar de confiança.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.meter_reading import same_reading


def rate(mask) -> str:
    return f"{mask.mean():.1%} ({int(mask.sum())}/{len(mask)})" if len(mask) else "n/a"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--review", type=Path, default=Path("data/review/review.csv"))
    parser.add_argument("--predictions", type=Path, default=Path("models/checkpoints/recognizer/test_predictions.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review = pd.read_csv(args.review, dtype={"human_reading": str}, keep_default_na=False)
    predictions = pd.read_csv(args.predictions, dtype={"label": str, "reading": str}, keep_default_na=False)
    df = review.merge(predictions, on=["image", "lot"], how="inner")

    illegible = df["illegible"].astype(str) == "1"
    legible = df[~illegible].copy()
    legible["model_ok"] = [same_reading(a, b) for a, b in zip(legible["reading"], legible["human_reading"])]
    legible["csv_ok"] = [same_reading(a, b) for a, b in zip(legible["label"], legible["human_reading"])]

    print(f"Conferidas: {len(df)} | ilegíveis: {rate(illegible)}")
    print(f"Modelo correto (legíveis):  {rate(legible['model_ok'])}")
    print(f"CSV correto (legíveis):     {rate(legible['csv_ok'])}")
    print("\nModelo por confiança (legíveis):")
    for level in (0.0, 0.5, 0.7, 0.9, 0.95):
        accepted = legible[legible["confidence"] >= level]
        print(f"  >= {level:<4}  cobertura {len(accepted) / max(len(legible), 1):.1%} | acerto {rate(accepted['model_ok'])}")
    print("\nConfiança média do modelo nas ilegíveis:", f"{df[illegible]['confidence'].mean():.2f}" if illegible.any() else "n/a")

    # O que importa em produção: das leituras aceitas automaticamente, quantas estão certas.
    # Foto ilegível aceita conta como erro: não há leitura que confirme o valor.
    df["ok"] = ~illegible & pd.Series([same_reading(a, b) for a, b in zip(df["reading"], df["human_reading"])], index=df.index)
    illegible_prob = df["illegible_prob"] if "illegible_prob" in df else pd.Series(0.0, index=df.index)
    rules = [("só confiança", 1.01)] + ([("ilegível < 0.5", 0.5)] if "illegible_prob" in df else [])
    for name, limit in rules:
        print(f"\nAceitas entre todas as conferidas ({name}):")
        for level in (0.5, 0.7, 0.9, 0.95):
            accepted = df[(df["confidence"] >= level) & (illegible_prob < limit)]
            wrong_illegible = int((accepted["illegible"].astype(str) == "1").sum())
            print(f"  >= {level:<4}  aceitas {len(accepted) / len(df):.1%} | acerto {rate(accepted['ok'])} | ilegíveis aceitas {wrong_illegible}")
    if "illegible_prob" in df:
        flagged = illegible_prob >= 0.5
        print(f"\nSaída de legibilidade (>= 0.5): marca {rate(flagged[illegible])} das ilegíveis e {rate(flagged[~illegible])} das legíveis")


if __name__ == "__main__":
    main()
