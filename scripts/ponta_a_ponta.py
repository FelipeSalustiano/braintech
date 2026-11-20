"""
Processa as fotos de teste do zero e publica o resultado no Supabase.

Etapas (cada uma é um script de pipelines/, rodado como na linha de comando):
  1. pré-processamento:  data/imgs_raw_test        -> data/imgs_preprocessed_test
  2. recorte do display:  detector de display        -> data/crops_display_test (+ manifest.csv)
  3. leitura do display:  reconhecedor (OCR)         -> data/readings/imgs_raw_test/readings.csv
  4. publicação:          fotos, recortes e leituras -> Supabase (scripts/supabase_carregar.py)

Antes de começar, confere se as fotos, os dois modelos e as chaves do Supabase estão no lugar,
e apaga as saídas de uma rodada anterior, para o resultado ser gerado de verdade agora.
Não treina nada: usa os modelos já treinados.

Roda na CPU de propósito, mesmo com GPU: na GPU o detector usa precisão reduzida (float16), e
nas fotos de confiança baixa isso muda a leitura. Na CPU o resultado é o mesmo em qualquer
máquina (testado em Windows e Linux, com 1 a 16 threads). No fim, o script confere se as
contagens batem com o resultado de referência (RESULTADO_ESPERADO).

Uso, na raiz do projeto:
    python scripts/ponta_a_ponta.py                 # processa e publica
    python scripts/ponta_a_ponta.py --sem-publicar  # só processa (não precisa do Supabase)
"""

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.supabase_api import load_dotenv  # noqa: E402

FOTOS = Path("data/imgs_raw_test")
PRE = Path("data/imgs_preprocessed_test")
RECORTES = Path("data/crops_display_test")
LEITURAS = Path("data/readings/imgs_raw_test")
DETECTOR_DISPLAY = Path("models/checkpoints/display/best.pt")
RECONHECEDOR = Path("models/checkpoints/recognizer/best.pt")

# Contagens por status das 18 fotos de data/imgs_raw_test, processadas na CPU.
RESULTADO_ESPERADO = {"lido": 2, "leitura_suspeita": 4, "ilegivel": 5, "sem_leitura": 7}


def checar(publicar: bool) -> list[str]:
    """Lista do que falta para rodar, com a instrução de como resolver."""
    faltas = []
    fotos = [p for p in (PROJECT_ROOT / FOTOS).glob("*") if p.suffix.lower() in (".jpg", ".jpeg")] \
        if (PROJECT_ROOT / FOTOS).is_dir() else []
    if not fotos:
        faltas.append(f"Nenhuma foto .jpg/.jpeg em {FOTOS}/ — as fotos de teste vêm com o git; rode `git pull`.")
    if not (PROJECT_ROOT / DETECTOR_DISPLAY).is_file():
        faltas.append(f"Falta o detector de display em {DETECTOR_DISPLAY} — baixe o best.pt do Drive (link no README, \"Demonstração de ponta a ponta\") e coloque-o nesse caminho.")
    if not (PROJECT_ROOT / RECONHECEDOR).is_file():
        faltas.append(f"Falta o reconhecedor em {RECONHECEDOR} — ele vem com o git; rode `git pull`.")
    if publicar:
        load_dotenv()
        if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SECRET_KEY"):
            faltas.append("Faltam SUPABASE_URL e SUPABASE_SECRET_KEY no .env da raiz (copie de .env.example).")
    return faltas


def etapa(numero: int, titulo: str, comando: list[str]) -> None:
    print(f"\n=== {numero}. {titulo} ===")
    print("$ python " + " ".join(f'"{c}"' if " " in c else c for c in comando))
    inicio = time.perf_counter()
    # Esconde a GPU dos pipelines para o resultado não depender da máquina (ver docstring).
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "-1"}
    resultado = subprocess.run([sys.executable, *comando], cwd=PROJECT_ROOT, env=env)
    if resultado.returncode != 0:
        raise SystemExit(f"\nA etapa {numero} falhou (código {resultado.returncode}). Veja a mensagem acima.")
    print(f"--- etapa {numero} concluída em {time.perf_counter() - inicio:.1f} s")


def conferir() -> None:
    """Compara as contagens por status com o resultado de referência."""
    with (PROJECT_ROOT / LEITURAS / "readings.csv").open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    obtido = {s: sum(1 for r in linhas if r["status"] == s) for s in RESULTADO_ESPERADO}
    resumo = ", ".join(f"{s}: {n}" for s, n in obtido.items())
    if obtido == RESULTADO_ESPERADO:
        print(f"\nResultado confere com o de referência ({len(linhas)} fotos — {resumo}).")
    else:
        esperado = ", ".join(f"{s}: {n}" for s, n in RESULTADO_ESPERADO.items())
        print(f"\nATENÇÃO: resultado diferente do de referência.\n  obtido:   {resumo}\n  esperado: {esperado}\n"
              "  Confira as versões de requirements.txt e se o detector de display é o arquivo do Drive.")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # mantém a ordem das mensagens junto com as das etapas
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sem-publicar", action="store_true", help="Só processa, não envia para o Supabase")
    args = parser.parse_args()
    publicar = not args.sem_publicar

    faltas = checar(publicar)
    if faltas:
        print("Antes de rodar, resolva:")
        for f in faltas:
            print("  - " + f)
        raise SystemExit(1)

    for pasta in (PRE, RECORTES, LEITURAS):  # saídas de uma rodada anterior
        shutil.rmtree(PROJECT_ROOT / pasta, ignore_errors=True)

    inicio = time.perf_counter()
    etapa(1, "Pré-processamento das fotos", [
        "pipelines/preprocessing_images.py", "--input", str(FOTOS), "--output", str(PRE)])
    etapa(2, "Recorte do display (detector)", [
        "pipelines/crop_detector.py", "--checkpoint", str(DETECTOR_DISPLAY), "--input", str(PRE),
        "--crop-source", str(FOTOS), "--output", str(RECORTES),
        "--threshold", "0.5", "--margin", "0.15", "--min-size", "8"])
    etapa(3, "Leitura do display (OCR)", [
        "pipelines/read_meter.py", "--input", str(RECORTES), "--output", str(LEITURAS)])
    conferir()
    if publicar:
        etapa(4, "Publicação no Supabase", ["scripts/supabase_carregar.py", "--lotes", "imgs_raw_test"])

    print(f"\nPronto em {time.perf_counter() - inicio:.0f} s. Leituras em {LEITURAS / 'readings.csv'}.")
    if publicar:
        print("Próximo passo: crie a conta (scripts/supabase_criar_usuario.py) e entre no painel (frontend: npm run dev).")


if __name__ == "__main__":
    main()
