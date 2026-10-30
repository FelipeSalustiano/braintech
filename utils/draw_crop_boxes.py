"""
Desenha a caixa de recorte de cada foto (lida do manifest.csv) para conferência visual.

Uso, na raiz do projeto:
    python utils/draw_crop_boxes.py
    python utils/draw_crop_boxes.py --images data/imgs_preprocessed_test --crops data/crops

Gera, em <crops>/conferencia/, uma imagem por foto com a caixa desenhada
(verde = recortado, laranja = caixa_cortada, vermelho = outros) e um painel
_painel.png com todas as fotos lado a lado.
"""

import argparse
import csv
from pathlib import Path

from PIL import Image, ImageDraw

STATUS_COLORS = {"recortado": "lime", "caixa_cortada": "orange"}
PANEL_CELL = (300, 400)
PANEL_COLUMNS = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images", type=Path, default=Path("data/imgs_preprocessed_test"), help="Imagens usadas no recorte (crop_source do config)")
    parser.add_argument("--crops", type=Path, default=Path("data/crops"), help="Pasta com o manifest.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.crops / "conferencia"
    output_dir.mkdir(parents=True, exist_ok=True)

    drawn = []
    with (args.crops / "manifest.csv").open(encoding="utf-8") as manifest_file:
        for row in csv.DictReader(manifest_file):
            image = Image.open(args.images / row["image"]).convert("RGB")
            draw = ImageDraw.Draw(image)
            line_width = max(2, image.width // 150)
            if row["left"]:
                box = [int(row[key]) for key in ("left", "top", "right", "bottom")]
                draw.rectangle(box, outline=STATUS_COLORS.get(row["status"], "red"), width=line_width)
            # Status e score no canto, para ler mesmo no painel reduzido.
            label = f"{row['status']} {row['score']}"
            draw.rectangle([0, 0, image.width, image.height // 14], fill="black")
            draw.text((8, 4), label, fill="yellow", font_size=max(12, image.height // 22))

            image.save(output_dir / f"{Path(row['image']).stem}.png")
            drawn.append(image)

    # Painel com todas as fotos, para conferir de uma vez.
    columns = min(PANEL_COLUMNS, max(1, len(drawn)))
    rows = (len(drawn) + columns - 1) // columns
    panel = Image.new("RGB", (PANEL_CELL[0] * columns, PANEL_CELL[1] * max(1, rows)), "white")
    for index, image in enumerate(drawn):
        thumbnail = image.copy()
        thumbnail.thumbnail(PANEL_CELL)
        panel.paste(thumbnail, ((index % columns) * PANEL_CELL[0], (index // columns) * PANEL_CELL[1]))
    panel.save(output_dir / "_painel.png")

    print(f"Conferência salva em {output_dir} ({len(drawn)} fotos + _painel.png)")


if __name__ == "__main__":
    main()
