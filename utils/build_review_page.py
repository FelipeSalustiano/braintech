"""
Gera uma página HTML local para conferir à mão a leitura de uma amostra do teste.

Os CSVs dos leituristas têm erros, então a acurácia contra eles mistura erro do
modelo com erro do gabarito. A página mostra o recorte do display e a foto
inteira; quem confere digita a leitura que vê (ou marca ilegível) e exporta um
CSV, que o utils/score_review.py compara com o modelo e com o CSV.

O campo começa vazio de propósito: mostrar a resposta do modelo induziria quem
confere a concordar com ela.

Uso, na raiz do projeto:
    python utils/build_review_page.py                                # 200 fotos do teste -> review.html
    python utils/build_review_page.py --subset train --size 600      # 3 páginas de 200 do treino

Cada página exporta um CSV com o próprio nome (review_train_01.html -> review_train_01.csv).

A página embute fotos de clientes: fica em data/review/, que não vai para o git.
"""

import argparse
import base64
import csv
import html
import json
import random
from pathlib import Path

import cv2

PAGE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conferência de leituras</title>
<style>
  :root {{ --bg: #f6f6f4; --card: #fff; --text: #1d1d1b; --muted: #6b6b66; --line: #ddd; --accent: #1f6feb; --done: #e8f3ea; --skip: #f6ece6; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #161615; --card: #20201e; --text: #ecece8; --muted: #9a9a94; --line: #34342f; --accent: #5b9bff; --done: #1d2b20; --skip: #2e221c; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font: 15px/1.4 system-ui, sans-serif; }}
  header {{ position: sticky; top: 0; z-index: 2; background: var(--bg); border-bottom: 1px solid var(--line); padding: 12px 16px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
  header h1 {{ font-size: 17px; margin: 0; }}
  .progress {{ color: var(--muted); }}
  button {{ font: inherit; padding: 6px 12px; border-radius: 6px; border: 1px solid var(--line); background: var(--card); color: var(--text); cursor: pointer; }}
  button.primary {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
  .help {{ color: var(--muted); font-size: 13px; width: 100%; }}
  main {{ max-width: 900px; margin: 0 auto; padding: 16px; display: grid; gap: 12px; }}
  .item {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px; display: grid; grid-template-columns: 1fr 110px; gap: 12px; }}
  .item.done {{ background: var(--done); }}
  .item.illegible {{ background: var(--skip); }}
  .display {{ width: 100%; image-rendering: auto; border-radius: 4px; }}
  .photo {{ width: 110px; border-radius: 4px; cursor: zoom-in; }}
  .controls {{ display: flex; gap: 10px; align-items: center; margin-top: 8px; flex-wrap: wrap; }}
  .controls input[type=text] {{ font: 22px/1 ui-monospace, monospace; width: 9ch; padding: 4px 8px; border-radius: 6px; border: 1px solid var(--line); background: var(--bg); color: var(--text); }}
  .num {{ color: var(--muted); font-size: 13px; }}
  dialog {{ border: none; padding: 0; background: transparent; }}
  dialog img {{ max-width: 92vw; max-height: 92vh; }}
  @media (max-width: 560px) {{ .item {{ grid-template-columns: 1fr; }} .photo {{ width: 100%; }} }}
</style>
</head>
<body>
<header>
  <h1>Conferência de leituras</h1>
  <span class="progress" id="progress"></span>
  <button class="primary" id="export">Exportar CSV</button>
  <div class="help">Digite a leitura que você vê no display (zeros à esquerda não importam) e aperte Enter para ir à próxima. Marque "ilegível" (atalho: tecla <b>i</b> com o campo vazio) quando não der para ler com certeza. Clique na foto para ampliar. O progresso fica salvo neste navegador.</div>
</header>
<main id="list"></main>
<dialog id="zoom"><img id="zoom-img" alt="Foto ampliada"></dialog>
<script>
const ITEMS = {items};
const KEY = "review:" + {key};
let state = {{}};
try {{ state = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{}}
function save() {{ try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}} }}

const list = document.getElementById("list");
ITEMS.forEach((item, i) => {{
  const s = state[item.image] || {{}};
  const el = document.createElement("div");
  el.className = "item";
  el.innerHTML = `
    <div>
      <div class="num">${{i + 1}} / ${{ITEMS.length}}</div>
      <img class="display" src="${{item.display}}" alt="Display">
      <div class="controls">
        <input type="text" inputmode="numeric" autocomplete="off" placeholder="leitura">
        <label><input type="checkbox"> ilegível</label>
      </div>
    </div>
    <img class="photo" src="${{item.photo}}" alt="Foto inteira">`;
  const input = el.querySelector("input[type=text]");
  const box = el.querySelector("input[type=checkbox]");
  input.value = s.reading || "";
  box.checked = !!s.illegible;
  function update() {{
    const reading = input.value.replace(/\\D/g, "");
    state[item.image] = {{ reading, illegible: box.checked }};
    el.classList.toggle("done", !!reading && !box.checked);
    el.classList.toggle("illegible", box.checked);
    save(); progress();
  }}
  input.addEventListener("input", update);
  box.addEventListener("change", update);
  input.addEventListener("keydown", e => {{
    if (e.key === "i" && !input.value) {{ e.preventDefault(); box.checked = !box.checked; update(); }}
    if (e.key === "Enter" || (e.key === "i" && !input.value)) {{
      const inputs = [...document.querySelectorAll("input[type=text]")];
      const next = inputs[inputs.indexOf(input) + 1];
      if (next) {{ next.focus(); next.scrollIntoView({{ block: "center", behavior: "smooth" }}); }}
    }}
  }});
  el.querySelector(".photo").addEventListener("click", () => {{
    document.getElementById("zoom-img").src = item.photo;
    document.getElementById("zoom").showModal();
  }});
  list.appendChild(el);
  if (s.reading || s.illegible) update();
}});
document.getElementById("zoom").addEventListener("click", e => e.currentTarget.close());

function progress() {{
  const done = ITEMS.filter(it => state[it.image] && (state[it.image].reading || state[it.image].illegible)).length;
  document.getElementById("progress").textContent = `${{done}} de ${{ITEMS.length}} conferidas`;
}}
progress();

document.getElementById("export").addEventListener("click", () => {{
  const rows = [["image", "lot", "human_reading", "illegible"]];
  ITEMS.forEach(it => {{
    const s = state[it.image] || {{}};
    if (s.reading || s.illegible) rows.push([it.image, it.lot, s.illegible ? "" : s.reading, s.illegible ? "1" : "0"]);
  }});
  const csv = rows.map(r => r.map(v => `"${{String(v).replace(/"/g, '""')}}"`).join(",")).join("\\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {{ type: "text/csv" }}));
  a.download = {csv_name};
  a.click();
}});
document.querySelector("input[type=text]")?.focus();
</script>
</body>
</html>
"""


def data_uri(path: Path, quality: int, max_side: int | None = None) -> str:
    """Imagem recodificada em JPEG e embutida em base64, para a página ficar leve."""
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"Image not found: {path}")
    if max_side and max(image.shape[:2]) > max_side:
        scale = max_side / max(image.shape[:2])
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError(f"Could not encode {path}")
    return f"data:image/jpeg;base64,{base64.b64encode(encoded.tobytes()).decode()}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", type=Path, default=Path("models/checkpoints/recognizer/split.csv"))
    parser.add_argument("--crops-root", type=Path, default=Path("data/display_crops"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw_images"))
    parser.add_argument("--subset", default="test", choices=["test", "validation", "train"], help="Conjunto do split.csv de onde vêm as fotos")
    parser.add_argument("--size", type=int, default=200, help="Total de fotos")
    parser.add_argument("--batch-size", type=int, default=200, help="Fotos por página (páginas grandes ficam pesadas no navegador)")
    parser.add_argument("--output-dir", type=Path, default=Path("data/review"))
    parser.add_argument("--name", help="Nome base das páginas (padrão: review para test, review_<subset> para os outros)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--photo-quality", type=int, default=60, help="Qualidade JPEG da foto inteira (1-100)")
    parser.add_argument("--photo-max-side", type=int, default=480, help="Maior lado da foto inteira, em pixels")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.split.open(encoding="utf-8") as split_file:
        rows = [row for row in csv.DictReader(split_file) if row["split"] == args.subset]
    # Embaralha tudo e fatia: gerar mais páginas depois mantém as mesmas fotos nas primeiras
    random.Random(args.seed).shuffle(rows)
    rows = rows[:args.size]
    name = args.name or ("review" if args.subset == "test" else f"review_{args.subset}")
    batches = [rows[start:start + args.batch_size] for start in range(0, len(rows), args.batch_size)]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for number, batch in enumerate(batches, start=1):
        stem = name if len(batches) == 1 else f"{name}_{number:02d}"
        items = [
            {
                "image": row["image"],
                "lot": row["lot"],
                # O display é onde se lê: qualidade alta. A foto inteira só dá contexto.
                "display": data_uri(args.crops_root / row["lot"] / f"{Path(row['image']).stem}.png", quality=90),
                "photo": data_uri(args.raw_root / row["lot"] / row["image"], quality=args.photo_quality, max_side=args.photo_max_side),
            }
            for row in batch
        ]
        # O JSON vai dentro de <script>: "</" fecharia a tag antes da hora
        items_json = json.dumps(items).replace("</", "<\\/")
        page = PAGE.format(
            items=items_json,
            key=json.dumps(html.escape(f"{stem}:{args.seed}:{len(items)}")),
            csv_name=json.dumps(f"{stem}.csv"),
        )
        output = args.output_dir / f"{stem}.html"
        output.write_text(page, encoding="utf-8")
        print(f"Página com {len(items)} fotos: {output.resolve()}")


if __name__ == "__main__":
    main()
