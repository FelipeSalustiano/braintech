"""Une as planilhas por rotulador em rotulos/rotulos.csv e calcula kappa de Cohen nos duplos.
Uso: python kappa.py   (roda de qualquer pasta)
"""
import csv
from collections import defaultdict
from pathlib import Path

CLASSES = ["legivel", "ilegivel", "nao_medidor"]
pasta = Path(__file__).resolve().parent.parent / "rotulos"

por_foto = defaultdict(dict)
lote = {}
for arq in sorted(pasta.glob("rotulos_*.csv")):
    for r in csv.DictReader(open(arq, encoding="utf-8")):
        if r["rotulo"].strip():
            por_foto[r["nome_arquivo"]][r["rotulador"]] = r["rotulo"].strip()
            lote[r["nome_arquivo"]] = r["lote"]

# rotulos.csv: um rótulo final por foto (nos duplos, o do 1º rotulador por ordem alfabética;
# a resolução de discordância pelo grupo deve ser feita à mão e registrada no README).
with open(pasta / "rotulos.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["nome_arquivo", "lote", "rotulador", "rotulo"])
    for n in sorted(por_foto):
        quem = sorted(por_foto[n])[0]
        w.writerow([n, lote[n], quem, por_foto[n][quem]])


def kappa(par):
    n = len(par)
    po = sum(a == b for a, b in par) / n
    pe = sum((sum(a == k for a, _ in par) / n) * (sum(b == k for _, b in par) / n) for k in (0, 1))
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


duplos = [(n, v) for n, v in por_foto.items() if len(v) == 2]
print(f"fotos rotuladas: {len(por_foto)} | duplos: {len(duplos)}")
if duplos:
    pares = [tuple(v[k] for k in sorted(v)) for _, v in duplos]
    print(f"concordância bruta: {sum(a == b for a, b in pares) / len(pares):.2f}")
    for c in CLASSES:
        k = kappa([(a == c, b == c) for a, b in pares])
        print(f"  kappa {c:<12} = {k:.3f}" + ("   <-- < 0,6: reescrever esquema" if k < 0.6 else ""))
    # kappa multiclasse
    n = len(pares)
    po = sum(a == b for a, b in pares) / n
    pe = sum((sum(a == c for a, _ in pares) / n) * (sum(b == c for _, b in pares) / n) for c in CLASSES)
    print(f"  kappa multiclasse = {(po - pe) / (1 - pe):.3f}")
