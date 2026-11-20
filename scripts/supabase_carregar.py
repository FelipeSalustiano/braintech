"""
Carrega fotos, recortes e leituras no Supabase para o painel VoltLens.

Por padrão manda só o lote de teste (data/imgs_raw_test, fotos do WhatsApp). Os lotes
PSP_* são opcionais: --lotes PSP_EXTRATLEITIMPL_030726_0121 ... ou --lotes todos.

Para cada foto:
- sobe a foto (JPEG reduzido) e o recorte do display (PNG) no bucket privado "leituras";
- grava (ou atualiza) a linha em public.leituras com a sugestão do OCR, o registro do
  PDA e o gabarito (leitura dos dados em src/voltlens_dados.py).

Pode rodar de novo sem duplicar nada: imagens já enviadas são puladas e as linhas
são atualizadas pelo par (lote, foto).

Precisa de SUPABASE_URL e SUPABASE_SECRET_KEY no arquivo .env da raiz (veja .env.example).
A chave secreta ignora as regras de acesso: nunca a coloque no front-end nem no git.

Uso, na raiz do projeto:
    python scripts/supabase_carregar.py                     # só o lote de teste
    python scripts/supabase_carregar.py --lotes todos --amostra 150
"""

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.supabase_api import Supabase  # noqa: E402
from src.voltlens_dados import (  # noqa: E402
    STATUS, TEST_SET, cmp_pda, load_expected, load_pda, num, read_rows, sample_rows, sources,
)

BUCKET = "leituras"


def object_name(name: str, suffix: str) -> str:
    """Nome seguro para o Storage (sem espaços nem parênteses)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("_") + suffix


def jpeg_bytes(path: Path, max_side: int, quality: int) -> bytes:
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"não consegui ler {path}")
    h, w = image.shape[:2]
    scale = max_side / max(h, w)
    if scale < 1:
        image = cv2.resize(image, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError(f"não consegui codificar {path}")
    return buf.tobytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lotes", nargs="+", default=[TEST_SET],
                        help=f"Lotes a carregar (padrão: {TEST_SET}). 'todos' carrega todos os lotes de data/readings")
    parser.add_argument("--amostra", type=int, default=0,
                        help="Fotos por lote (amostra estratificada por status). 0 = todas")
    parser.add_argument("--foto-lado", type=int, default=1600, help="Maior lado da foto enviada, em px")
    parser.add_argument("--foto-qualidade", type=int, default=80)
    parser.add_argument("--sem-imagens", action="store_true", help="Só grava as linhas, sem subir imagens")
    parser.add_argument("--workers", type=int, default=8, help="Envios em paralelo")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    sb = Supabase.from_env()
    todos = sources()
    if args.lotes != ["todos"]:
        pedidos = set(args.lotes)
        desconhecidos = pedidos - {lote.id for lote in todos}
        if desconhecidos:
            parser.error(f"lote(s) sem data/readings/<lote>/readings.csv: {', '.join(sorted(desconhecidos))}")
        todos = [lote for lote in todos if lote.id in pedidos]

    expected = load_expected()
    pda = load_pda()
    print(f"Supabase: {sb.url}")

    for ordem_lote, lote in enumerate(todos):
        rows = sample_rows(read_rows(lote), args.amostra, expected, args.seed)
        sb.upsert("lotes", [{"id": lote.id, "nome": lote.nome, "ordem": ordem_lote}], on_conflict="id")

        existentes = set() if args.sem_imagens else sb.list_objects(BUCKET, lote.id)
        uploads, linhas = [], []
        for ordem, row in enumerate(rows):
            if row["status"] not in STATUS:
                raise ValueError(f"{lote.id}/{row['image']}: status desconhecido {row['status']!r}")
            image = row["image"]
            foto = lote.fotos / image
            recorte = lote.recortes / Path(image).with_suffix(".png").name
            foto_path = f"{lote.id}/fotos/{object_name(image, '.jpg')}" if foto.is_file() else None
            recorte_path = f"{lote.id}/recortes/{object_name(image, '.png')}" if recorte.is_file() else None
            if not args.sem_imagens:
                if foto_path and foto_path not in existentes:
                    uploads.append((foto_path, foto, "image/jpeg"))
                if recorte_path and recorte_path not in existentes:
                    uploads.append((recorte_path, recorte, "image/png"))
            rec = pda.get(image, {})
            linhas.append({
                "lote_id": lote.id,
                "ordem": ordem,
                "foto": image,
                "foto_path": foto_path,
                "recorte_path": recorte_path,
                "status": row["status"],
                "leitura": row["reading"] or None,
                "confianca": num(row["confidence"]),
                "prob_ilegivel": num(row["illegible_prob"]),
                "score_deteccao": num(row["detection_score"]),
                "medidor": rec.get("m") or None,
                "leitura_pda": rec.get("l") or None,
                "nota": rec.get("n") or None,
                "cmp_pda": cmp_pda(row["reading"], rec.get("l")),
                "gabarito": expected.get(image),
            })

        def enviar(item: tuple[str, Path, str]) -> None:
            path, local, content_type = item
            body = jpeg_bytes(local, args.foto_lado, args.foto_qualidade) if content_type == "image/jpeg" else local.read_bytes()
            sb.upload(BUCKET, path, body, content_type)

        if uploads:
            with ThreadPoolExecutor(args.workers) as pool:
                for i, _ in enumerate(pool.map(enviar, uploads), 1):
                    if i % 100 == 0 or i == len(uploads):
                        print(f"  {lote.id}: {i}/{len(uploads)} imagens enviadas")
        for start in range(0, len(linhas), 500):
            sb.upsert("leituras", linhas[start:start + 500], on_conflict="lote_id,foto")
        print(f"{lote.id}: {len(linhas)} leituras, {len(uploads)} imagens novas"
              f" ({len(existentes)} já estavam no bucket)")


if __name__ == "__main__":
    main()
