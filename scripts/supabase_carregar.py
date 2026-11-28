"""
Publica no Supabase o resultado do processamento (recortes e leituras) para o painel VoltLens.

Por padrão manda só o lote de teste (data/imgs_raw_test, fotos do WhatsApp). Os lotes
PSP_* são opcionais: --lotes PSP_EXTRATLEITIMPL_030726_0121 ... ou --lotes todos.

As fotos já estão no Supabase (enviadas por scripts/supabase_enviar_fotos.py, em
<lote>/fotos/ do bucket "leituras"): este script não as envia de novo. Para cada foto:
- aponta a linha para a foto que já está no bucket (o painel a mostra de lá);
- sobe o recorte do display (PNG) em <lote>/recortes/;
- grava (ou atualiza) a linha em public.leituras com a sugestão do OCR, o registro do
  PDA e o gabarito (leitura dos dados em src/voltlens_dados.py).

Pode rodar de novo sem duplicar nada: recortes já enviados são pulados e as linhas
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.supabase_api import Supabase  # noqa: E402
from src.voltlens_dados import (  # noqa: E402
    STATUS, TEST_SET, cmp_pda, load_expected, load_pda, num, read_rows, sample_rows, sources,
)

BUCKET = "leituras"


def object_name(name: str, suffix: str) -> str:
    """Nome seguro para o Storage (sem espaços nem parênteses)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("_") + suffix


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lotes", nargs="+", default=[TEST_SET],
                        help=f"Lotes a carregar (padrão: {TEST_SET}). 'todos' carrega todos os lotes de data/readings")
    parser.add_argument("--amostra", type=int, default=0,
                        help="Fotos por lote (amostra estratificada por status). 0 = todas")
    parser.add_argument("--sem-imagens", action="store_true", help="Só grava as linhas, sem subir recortes")
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

        existentes = sb.list_objects(BUCKET, lote.id)
        uploads, linhas, sem_foto = [], [], []
        for ordem, row in enumerate(rows):
            if row["status"] not in STATUS:
                raise ValueError(f"{lote.id}/{row['image']}: status desconhecido {row['status']!r}")
            image = row["image"]
            recorte = lote.recortes / Path(image).with_suffix(".png").name
            foto_path = f"{lote.id}/fotos/{image}"  # mesmo nome com que scripts/supabase_enviar_fotos.py enviou
            if foto_path not in existentes:
                sem_foto.append(image)
                foto_path = None
            recorte_path = f"{lote.id}/recortes/{object_name(image, '.png')}" if recorte.is_file() else None
            if not args.sem_imagens and recorte_path and recorte_path not in existentes:
                uploads.append((recorte_path, recorte))
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

        def enviar(item: tuple[str, Path]) -> None:
            path, local = item
            sb.upload(BUCKET, path, local.read_bytes(), "image/png")

        if uploads:
            with ThreadPoolExecutor(args.workers) as pool:
                for i, _ in enumerate(pool.map(enviar, uploads), 1):
                    if i % 100 == 0 or i == len(uploads):
                        print(f"  {lote.id}: {i}/{len(uploads)} recortes enviados")
        for start in range(0, len(linhas), 500):
            sb.upsert("leituras", linhas[start:start + 500], on_conflict="lote_id,foto")
        print(f"{lote.id}: {len(linhas)} leituras, {len(uploads)} recortes novos")
        if sem_foto:
            print(f"  aviso: {len(sem_foto)} foto(s) não estão em {BUCKET}/{lote.id}/fotos/ e vão aparecer sem foto no painel"
                  f" (envie com scripts/supabase_enviar_fotos.py). Ex.: {sem_foto[0]}")


if __name__ == "__main__":
    main()
