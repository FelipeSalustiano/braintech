"""
Apaga do Supabase os dados do painel VoltLens, para começar do zero (ex.: antes de uma apresentação).

Apaga: as imagens do bucket "leituras", as linhas de decisoes, questionarios, leituras e
lotes e, com --contas, as contas do painel (e-mails @voltlens.local). As tabelas, as
regras de acesso e o bucket continuam lá: depois é só rodar scripts/ponta_a_ponta.py.

Usa SUPABASE_URL e SUPABASE_SECRET_KEY do .env da raiz. Pede confirmação antes de apagar.

Uso, na raiz do projeto:
    python scripts/supabase_limpar.py            # dados e imagens
    python scripts/supabase_limpar.py --contas   # dados, imagens e contas
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.supabase_api import Supabase  # noqa: E402

BUCKET = "leituras"
TABELAS = [("decisoes", "id"), ("questionarios", "lote_id"), ("leituras", "id"), ("lotes", "id")]  # filhas antes das mães


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--contas", action="store_true", help="Apaga também as contas do painel")
    parser.add_argument("--sim", action="store_true", help="Não pede confirmação")
    args = parser.parse_args()

    sb = Supabase.from_env()
    dominio = "@" + os.environ.get("VOLTLENS_LOGIN_DOMAIN", "voltlens.local")
    objetos = sorted(sb.list_objects(BUCKET, ""))
    contagens = {t: sb.count(t) for t, _ in TABELAS}
    contas = [u for u in sb.list_users() if (u.get("email") or "").endswith(dominio)] if args.contas else []

    print(f"Supabase: {sb.url}")
    print(f"  imagens no bucket '{BUCKET}': {len(objetos)}")
    for t, n in contagens.items():
        print(f"  linhas em {t}: {n}")
    if args.contas:
        print(f"  contas {dominio}: {', '.join(u['email'] for u in contas) or 'nenhuma'}")
    if not objetos and not any(contagens.values()) and not contas:
        print("Nada para apagar.")
        return
    if not args.sim and input("Apagar tudo isso? Não dá para desfazer. Digite 'apagar': ").strip() != "apagar":
        print("Cancelado.")
        return

    sb.delete_objects(BUCKET, objetos)
    for tabela, coluna in TABELAS:
        sb.delete_all(tabela, coluna)
    for u in contas:
        sb.delete_user(u["id"])
    print(f"Apagado: {len(objetos)} imagens, {sum(contagens.values())} linhas, {len(contas)} contas.")


if __name__ == "__main__":
    main()
