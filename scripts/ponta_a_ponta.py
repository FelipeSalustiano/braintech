"""
Baixa as fotos de teste do Supabase, processa do zero e publica o resultado no Supabase.

Etapas:
  0. download:            Supabase (leituras/imgs_raw_test/fotos/) -> data/entrada/imgs_raw_test
  1. pré-processamento:   pipelines/preprocessing_images.py         -> data/imgs_preprocessed_test
  2. recorte do display:  pipelines/crop_detector.py (detector)     -> data/crops_display_test (+ manifest.csv)
  3. leitura do display:  pipelines/read_meter.py (reconhecedor)    -> data/readings/imgs_raw_test/readings.csv
  4. publicação:          scripts/supabase_carregar.py              -> Supabase (recortes e leituras)

As fotos entram no Supabase uma vez, com scripts/supabase_enviar_fotos.py. Depois da etapa 4,
o painel mostra cada foto direto do Supabase, ao lado do recorte e da leitura.

Antes de começar, confere se os dois modelos e as chaves do Supabase estão no lugar e se as
fotos estão no Supabase, e apaga as saídas de uma rodada anterior, para o resultado ser gerado
de verdade agora. Não treina nada: usa os modelos já treinados.

Roda na CPU de propósito, mesmo com GPU: na GPU o detector usa precisão reduzida (float16), e
nas fotos de confiança baixa isso muda a leitura. Na CPU o resultado é o mesmo em qualquer
máquina (testado em Windows e Linux, com 1 a 16 threads). No fim, o script confere se as
contagens batem com o resultado de referência (RESULTADO_ESPERADO).

Uso, na raiz do projeto:
    python scripts/ponta_a_ponta.py                 # baixa, processa e publica
    python scripts/ponta_a_ponta.py --sem-publicar  # baixa e processa, sem publicar
"""

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.supabase_api import Supabase, load_dotenv  # noqa: E402

LOTE = "imgs_raw_test"
BUCKET = "leituras"
ENTRADA = Path("data/entrada") / LOTE          # fotos baixadas do Supabase (fora do git)
PRE = Path("data/imgs_preprocessed_test")
RECORTES = Path("data/crops_display_test")
LEITURAS = Path("data/readings") / LOTE
DETECTOR_DISPLAY = Path("models/checkpoints/display/best.pt")
RECONHECEDOR = Path("models/checkpoints/recognizer/best.pt")

# Contagens por status das 18 fotos de teste, processadas na CPU.
RESULTADO_ESPERADO = {"lido": 2, "leitura_suspeita": 4, "ilegivel": 5, "sem_leitura": 7}


def checar() -> list[str]:
    """Lista do que falta para rodar, com a instrução de como resolver."""
    faltas = []
    if not (PROJECT_ROOT / DETECTOR_DISPLAY).is_file():
        faltas.append(f"Falta o detector de display em {DETECTOR_DISPLAY} — baixe o best.pt do Drive (link no README, \"Demonstração de ponta a ponta\") e coloque-o nesse caminho.")
    if not (PROJECT_ROOT / RECONHECEDOR).is_file():
        faltas.append(f"Falta o reconhecedor em {RECONHECEDOR} — ele vem com o git; rode `git pull`.")
    load_dotenv()
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SECRET_KEY"):
        faltas.append("Faltam SUPABASE_URL e SUPABASE_SECRET_KEY no .env da raiz (copie de .env.example).")
    return faltas


def titulo_etapa(numero: int, titulo: str) -> float:
    print(f"\n=== {numero}. {titulo} ===")
    return time.perf_counter()


def baixar_fotos(sb: Supabase) -> None:
    inicio = titulo_etapa(0, "Download das fotos do Supabase")
    prefixo = f"{LOTE}/fotos"
    caminhos = sorted(p for p in sb.list_objects(BUCKET, prefixo) if p.lower().endswith((".jpg", ".jpeg")))
    if not caminhos:
        raise SystemExit(f"Nenhuma foto em {BUCKET}/{prefixo}/ no Supabase. Envie as fotos de teste uma vez com:\n"
                         "  python scripts/supabase_enviar_fotos.py")
    destino = PROJECT_ROOT / ENTRADA
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    def baixar(caminho: str) -> None:
        (destino / Path(caminho).name).write_bytes(sb.download(BUCKET, caminho))

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(baixar, caminhos))
    print(f"{len(caminhos)} fotos de {sb.url}/…/{BUCKET}/{prefixo}/ -> {ENTRADA}")
    print(f"--- etapa 0 concluída em {time.perf_counter() - inicio:.1f} s")


def etapa(numero: int, titulo: str, comando: list[str]) -> None:
    inicio = titulo_etapa(numero, titulo)
    print("$ python " + " ".join(f'"{c}"' if " " in c else c for c in comando))
    resultado = subprocess.run([sys.executable, *comando], cwd=PROJECT_ROOT)
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
              "  Confira as versões de requirements.txt, se o detector de display é o arquivo do Drive e\n"
              "  se as fotos no Supabase são as 18 de data/imgs_raw_test.")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)  # mantém a ordem das mensagens junto com as das etapas
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sem-publicar", action="store_true", help="Baixa e processa, mas não publica no Supabase")
    args = parser.parse_args()

    faltas = checar()
    if faltas:
        print("Antes de rodar, resolva:")
        for f in faltas:
            print("  - " + f)
        raise SystemExit(1)
    sb = Supabase.from_env()

    for pasta in (PRE, RECORTES, LEITURAS):  # saídas de uma rodada anterior
        shutil.rmtree(PROJECT_ROOT / pasta, ignore_errors=True)

    inicio = time.perf_counter()
    baixar_fotos(sb)
    etapa(1, "Pré-processamento das fotos", [
        "pipelines/preprocessing_images.py", "--input", str(ENTRADA), "--output", str(PRE)])
    etapa(2, "Recorte do display (detector)", [
        "pipelines/crop_detector.py", "--checkpoint", str(DETECTOR_DISPLAY), "--input", str(PRE),
        "--crop-source", str(ENTRADA), "--output", str(RECORTES),
        "--threshold", "0.5", "--margin", "0.15", "--min-size", "8", "--device", "cpu"])
    etapa(3, "Leitura do display (OCR)", [
        "pipelines/read_meter.py", "--input", str(RECORTES), "--output", str(LEITURAS),
        "--device", "cpu"])
    conferir()
    if not args.sem_publicar:
        etapa(4, "Publicação no Supabase", ["scripts/supabase_carregar.py", "--lotes", LOTE])

    print(f"\nPronto em {time.perf_counter() - inicio:.0f} s. Leituras em {LEITURAS / 'readings.csv'}.")
    if not args.sem_publicar:
        print("Próximo passo: crie a conta (scripts/supabase_criar_usuario.py) e entre no painel (frontend: npm run dev).")


if __name__ == "__main__":
    main()
