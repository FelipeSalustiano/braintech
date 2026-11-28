"""
Envia as fotos de um lote para o Supabase, onde o processamento vai buscá-las.

As fotos vão sem alteração (mesmos bytes e mesmo nome) para o bucket privado "leituras",
em <lote>/fotos/. Daí:
- scripts/ponta_a_ponta.py baixa as fotos de lá, processa e publica o resultado;
- o painel mostra a foto direto desse caminho.

Basta rodar uma vez por lote (ou quando chegarem fotos novas): fotos já enviadas são puladas.
O scripts/supabase_limpar.py mantém as fotos de entrada, a menos que receba --fotos.

Precisa de SUPABASE_URL e SUPABASE_SECRET_KEY no .env da raiz.

Uso, na raiz do projeto:
    python scripts/supabase_enviar_fotos.py                          # fotos de teste: data/imgs_raw_test
    python scripts/supabase_enviar_fotos.py --pasta <pasta> --lote <nome-do-lote>
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.supabase_api import Supabase  # noqa: E402
from src.voltlens_dados import DATA, TEST_SET  # noqa: E402

BUCKET = "leituras"
TIPOS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pasta", type=Path, default=DATA / TEST_SET, help="Pasta com as fotos (padrão: data/imgs_raw_test)")
    parser.add_argument("--lote", default=TEST_SET, help=f"Nome do lote no Supabase (padrão: {TEST_SET})")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    fotos = sorted(p for p in args.pasta.glob("*") if p.suffix.lower() in TIPOS)
    if not fotos:
        raise SystemExit(f"Nenhuma foto .jpg/.jpeg/.png em {args.pasta}")
    sb = Supabase.from_env()
    prefixo = f"{args.lote}/fotos"
    existentes = sb.list_objects(BUCKET, prefixo)
    novas = [p for p in fotos if f"{prefixo}/{p.name}" not in existentes]

    def enviar(p: Path) -> None:
        sb.upload(BUCKET, f"{prefixo}/{p.name}", p.read_bytes(), TIPOS[p.suffix.lower()])

    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(enviar, novas))
    print(f"{sb.url}: {len(novas)} fotos enviadas para {BUCKET}/{prefixo}/ "
          f"({len(fotos) - len(novas)} já estavam lá; {len(fotos)} na pasta)")


if __name__ == "__main__":
    main()
