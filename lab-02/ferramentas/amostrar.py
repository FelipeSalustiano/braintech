"""Sorteia a amostra de rotulagem estratificada por lote e gera as planilhas por rotulador.

Uso:
  python amostrar.py --fotos <pasta_com_subpastas_por_lote> --rotuladores ana,bia,caio,davi,edu \
      [--n 300] [--n-duplos 50] [--seed 42]

Espera <fotos>/<lote>/*.jpg (uma subpasta por extração). Lê só nomes de arquivo: nenhuma foto é copiada.
Saída (em lab-02/rotulos/): amostra.csv (mestre) e rotulos_<nome>.csv (uma planilha por pessoa).
Os 50 duplos vão para exatamente 2 rotuladores, cada um recebendo a sua planilha sem saber o par.
"""
import argparse
import csv
import random
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--fotos", required=True)
ap.add_argument("--rotuladores", required=True)
ap.add_argument("--n", type=int, default=300)
ap.add_argument("--n-duplos", type=int, default=50)
ap.add_argument("--seed", type=int, default=42)
a = ap.parse_args()

rng = random.Random(a.seed)
raiz = Path(a.fotos)
pessoas = a.rotuladores.split(",")
lotes = sorted(p for p in raiz.iterdir() if p.is_dir())
por_lote = {l.name: sorted(f.name for f in l.iterdir() if f.suffix.lower() in {".jpg", ".jpeg"}) for l in lotes}
cota = a.n // len(lotes)
amostra = []
for lote, nomes in por_lote.items():
    amostra += [(n, lote) for n in rng.sample(nomes, min(cota, len(nomes)))]
rng.shuffle(amostra)

duplos = set(range(a.n_duplos))  # índices (já embaralhados) que terão dois rotuladores
atrib = {p: [] for p in pessoas}
for i, (nome, lote) in enumerate(amostra):
    donos = [pessoas[i % len(pessoas)]]
    if i in duplos:
        donos.append(pessoas[(i + 1) % len(pessoas)])
    for d in donos:
        atrib[d].append((nome, lote))

out = Path(__file__).resolve().parent.parent / "rotulos"
with open(out / "amostra.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["nome_arquivo", "lote", "duplo"])
    for i, (n, l) in enumerate(amostra):
        w.writerow([n, l, int(i in duplos)])
for p, linhas in atrib.items():
    with open(out / f"rotulos_{p}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nome_arquivo", "lote", "rotulador", "rotulo"])  # rotulo: legivel|ilegivel|nao_medidor
        for n, l in sorted(linhas):  # ordem alfabética: não revela quais são duplos
            w.writerow([n, l, p, ""])
print({l: min(cota, len(n)) for l, n in por_lote.items()}, "total", len(amostra))
