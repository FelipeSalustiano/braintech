"""
Pega todas as fotos da pasta "data", embaralha e divide em:

    data_for_model/
    ├── train_dataset/   (70%)
    └── test_dataset/    (30%)
"""

import argparse
import random
import shutil
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def find_images(source: Path, exclude: Path) -> list[Path]:
    """Busca recursivamente todas as imagens dentro de `source`."""
    exclude = exclude.resolve()
    images = []
    for path in source.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        # ignora arquivos que já estejam na pasta de saída
        if exclude in path.resolve().parents:
            continue
        images.append(path)
    return sorted(images)  # ordena antes do shuffle para garantir reprodutibilidade


def unique_name(image: Path, source: Path) -> str:
    """
    Gera um nome único usando a subpasta de origem como prefixo,
    evitando que fotos com o mesmo nome em pastas diferentes se sobrescrevam.
    Ex.: PSP_EXTRATLEITIMPL_030726_0121__IMG_0001.jpg
    """
    relative_parent = image.parent.relative_to(source)
    prefix = "_".join(relative_parent.parts)
    return f"{prefix}__{image.name}" if prefix else image.name


def copy_files(images: list[Path], dest: Path, source: Path, move: bool) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    action = shutil.move if move else shutil.copy2
    for image in images:
        action(str(image), str(dest / unique_name(image, source)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Divide imagens em treino e teste.")
    parser.add_argument("--source", default="data/meter_images",
                        help="Pasta com as fotos (busca recursiva).")
    parser.add_argument("--output", default="data/data_for_model",
                        help="Pasta de saída (será criada).")
    parser.add_argument("--train-ratio", type=float, default=0.7,
                        help="Proporção de treino (padrão: 0.7).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Seed do shuffle, para resultados reproduzíveis.")
    parser.add_argument("--move", action="store_true",
                        help="Move os arquivos em vez de copiar.")
    args = parser.parse_args()

    source = Path(args.source)
    output = Path(args.output)

    if not source.is_dir():
        raise SystemExit(f"Pasta de origem não encontrada: {source}")
    if not 0 < args.train_ratio < 1:
        raise SystemExit("--train-ratio deve estar entre 0 e 1.")

    images = find_images(source, exclude=output)
    if not images:
        raise SystemExit(f"Nenhuma imagem encontrada em {source}")

    # Shuffle (Fisher-Yates via random.shuffle) com seed fixa
    random.Random(args.seed).shuffle(images)

    split_index = int(len(images) * args.train_ratio)
    train_images = images[:split_index]
    test_images = images[split_index:]

    train_dir = output / "train_dataset"
    test_dir = output / "test_dataset"

    # Limpa execuções anteriores para não misturar divisões diferentes
    for folder in (train_dir, test_dir):
        if folder.exists():
            shutil.rmtree(folder)

    copy_files(train_images, train_dir, source, args.move)
    copy_files(test_images, test_dir, source, args.move)

    total = len(images)
    print(f"Total de imagens: {total}")
    print(f"Treino: {len(train_images)} ({len(train_images) / total:.1%}) -> {train_dir}")
    print(f"Teste:  {len(test_images)} ({len(test_images) / total:.1%}) -> {test_dir}")


# if __name__ == "__main__":
#     main()