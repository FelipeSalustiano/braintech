"""
Cria uma conta para entrar no painel VoltLens.

O painel pede "Usuário" e "Senha". Por trás, o Supabase Auth usa e-mail: o usuário
"maria" vira o e-mail maria@voltlens.local (o domínio é só um rótulo, nenhum e-mail
é enviado). O cadastro pela própria tela está desligado de propósito: as fotos são
do cliente, então só entra quem recebeu uma conta.

Uso, na raiz do projeto:
    python scripts/supabase_criar_usuario.py maria "uma-senha-forte"
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.supabase_api import Supabase, SupabaseError, load_dotenv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("usuario")
    parser.add_argument("senha", help="Mínimo de 6 caracteres")
    args = parser.parse_args()

    load_dotenv()
    dominio = os.environ.get("VOLTLENS_LOGIN_DOMAIN", "voltlens.local")
    usuario = args.usuario.strip().lower()
    if not usuario or "@" in usuario:
        parser.error("use só o nome de usuário, sem @")
    sb = Supabase.from_env()
    try:
        sb.create_user(f"{usuario}@{dominio}", args.senha, {"usuario": usuario})
    except SupabaseError as e:
        raise SystemExit(f"Não consegui criar {usuario}: {e}")
    print(f"Conta criada: usuário '{usuario}' ({usuario}@{dominio}) em {sb.url}")


if __name__ == "__main__":
    main()
