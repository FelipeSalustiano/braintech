"""Compara as leituras com a coluna "Posicao do medidor lida" dos CSVs dos leituristas.

Leituras 0 no gabarito ficam fora por padrão: a EDA mostrou que elas marcam
falha de leitura do leiturista, não um valor real do display.

O reconhecedor foi treinado com fotos desses mesmos lotes. Para uma acurácia
honesta, use --only-test: avalia só as fotos do conjunto de teste (split.csv).

Saída, ao lado do readings.csv:
- evaluation.csv: cada foto avaliada com a leitura esperada e se acertou;
- o resumo das métricas no terminal.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.meter_reading import STATUS_LIDO, same_reading

PHOTO_COLUMN = "Foto do medidor"
READING_COLUMN = "Posicao do medidor lida"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def photo_key(name: str) -> str:
    """Nome da foto sem a extensão de imagem; o CSV pode ou não trazer a extensão.

    Não usa Path.stem direto: em nomes como "foto 21.05.53" o ".53" não é extensão.
    """
    path = Path(name.strip())
    return path.stem if path.suffix.lower() in IMAGE_EXTENSIONS else path.name


def load_ground_truth(sheets_dir: Path, keep_zeros: bool) -> pd.DataFrame:
    """Junta os CSVs e devolve uma linha por foto: (stem, expected)."""
    sheets = sorted(sheets_dir.glob("*.csv"))
    if not sheets:
        raise FileNotFoundError(f"No CSV found in {sheets_dir}")
    df = pd.concat([pd.read_csv(sheet, sep=";", dtype={PHOTO_COLUMN: str}) for sheet in sheets])
    df = df.dropna(subset=[PHOTO_COLUMN, READING_COLUMN])
    if not keep_zeros:
        df = df[df[READING_COLUMN] != 0]

    df["stem"] = df[PHOTO_COLUMN].map(photo_key)
    # Fotos citadas com leituras diferentes não servem de gabarito.
    conflicts = df.groupby("stem")[READING_COLUMN].nunique()
    df = df[df["stem"].isin(conflicts[conflicts == 1].index)]
    return df.drop_duplicates("stem")[["stem", READING_COLUMN]].rename(columns={READING_COLUMN: "expected"})


def rate(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.1%} ({numerator}/{denominator})" if denominator else "n/a"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path("configs/detector.json"))
    parser.add_argument("--readings", type=Path, help="Pasta com o readings.csv")
    parser.add_argument("--sheets", type=Path, default=Path("data/sheets"), help="Pasta com os CSVs dos leituristas")
    parser.add_argument("--keep-zeros", action="store_true", help="Avalia também as fotos com leitura 0 no gabarito")
    parser.add_argument("--only-test", action="store_true", help="Avalia só as fotos do conjunto de teste do reconhecedor")
    parser.add_argument("--split", type=Path, default=Path("models/checkpoints/recognizer/split.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = {}
    if args.config.is_file():
        with args.config.open(encoding="utf-8") as config_file:
            config = json.load(config_file)
    readings_dir = Path(args.readings or config.get("reading", {}).get("output", "data/readings"))

    readings = pd.read_csv(readings_dir / "readings.csv", dtype={"reading": str}, keep_default_na=False)
    if args.only_test:
        split = pd.read_csv(args.split)
        readings = readings[readings["image"].isin(split.loc[split["split"] == "test", "image"])]
    readings["stem"] = readings["image"].map(photo_key)
    truth = load_ground_truth(args.sheets, args.keep_zeros)

    df = readings.merge(truth, on="stem", how="inner")
    if df.empty:
        print("Nenhuma foto do readings.csv aparece nos CSVs: confira se as fotos são das mesmas extrações.")
        return
    df["correct"] = [same_reading(r, e) for r, e in zip(df["reading"], df["expected"])]
    df.drop(columns="stem").to_csv(readings_dir / "evaluation.csv", index=False)

    total = len(df)
    read = df[df["status"] == STATUS_LIDO]
    print(f"Fotos avaliadas: {total} (de {len(readings)} no readings.csv)")
    print(f"Acurácia ponta a ponta:     {rate(int(df['correct'].sum()), total)}")
    print(f"Cobertura (status 'lido'):  {rate(len(read), total)}")
    print(f"Acurácia entre as lidas:    {rate(int(read['correct'].sum()), len(read))}")

    for column in ("crop_status", "status"):
        print(f"\nPor {column}:")
        for value, group in df.groupby(column, dropna=False):
            print(f"  {value or '-':<20} {rate(int(group['correct'].sum()), len(group))}")

    print(f"\nDetalhe por foto: {readings_dir / 'evaluation.csv'}")


if __name__ == "__main__":
    main()
