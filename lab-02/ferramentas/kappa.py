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
EXTRAS = {"rotulos_finais", "rotulos_3"}   # consenso e 3º rotulador (v2) ficam fora da consolidação
for arq in sorted(p for p in pasta.glob("rotulos_*.csv") if p.stem not in EXTRAS):
    for r in csv.DictReader(open(arq, encoding="utf-8")):
        if r["rotulo"].strip():
            por_foto[r["nome_arquivo"]][r["rotulador"]] = r["rotulo"].strip()
            lote[r["nome_arquivo"]] = r["lote"]

# rotulos.csv: um rótulo final por foto. Acordo -> o rótulo comum; discordância -> o consenso
# registrado em rotulos_finais.csv (coluna rotulo_final). Sem consenso, cai no 1º rotulador.
final = {}
arq_final = pasta / "rotulos_finais.csv"
if arq_final.exists():
    final = {r["nome_arquivo"]: r["rotulo_final"].strip() for r in csv.DictReader(open(arq_final, encoding="utf-8"))}
with open(pasta / "rotulos.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["nome_arquivo", "lote", "rotulador", "rotulo"])
    for n in sorted(por_foto):
        v = por_foto[n]
        if len(set(v.values())) == 1:
            quem, rot = "+".join(sorted(v)), next(iter(v.values()))
        elif n in final:
            quem, rot = "consenso", final[n]
        else:
            quem = sorted(v)[0]; rot = v[quem]
        w.writerow([n, lote[n], quem, rot])


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


def relatorio(pares, titulo):
    n = len(pares)
    print(f"\n{titulo} (n={n}) | concordância bruta: {sum(a == b for a, b in pares) / n:.2f}")
    for c in CLASSES:
        k = kappa([(a == c, b == c) for a, b in pares])
        print(f"  kappa {c:<12} = {k:.3f}" + ("   <-- < 0,6" if k < 0.6 else ""))


# Subamostra dos 50 duplos exigidos pelo enunciado: estratificada por lote, semente fixa (definida
# antes de olhar as discordâncias, para não escolher a amostra pelo resultado).
if len(duplos) > 50:
    import random
    rng = random.Random(42)
    lotes = sorted({lote[n] for n, _ in duplos})
    sub = []
    for i, l in enumerate(lotes):
        cand = sorted(n for n, _ in duplos if lote[n] == l)
        sub += rng.sample(cand, 50 // len(lotes) + (1 if i < 50 % len(lotes) else 0))
    relatorio([tuple(por_foto[n][k] for k in sorted(por_foto[n])) for n in sub], "Subamostra de 50 duplos")

# Discordâncias para resolver em consenso (preencher rotulo_final e copiar para rotulos.csv).
if duplos:
    with open(pasta / "discordancias.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        quem = sorted(duplos[0][1])
        w.writerow(["nome_arquivo", "lote", *quem, "rotulo_final"])
        for n, v in sorted(duplos):
            if len(set(v.values())) > 1:
                w.writerow([n, lote[n], *[v[k] for k in quem], ""])


# Terceiro rotulador (Kevin, esquema v2, às cegas): kappa contra cada rotulador da v1.
arq_k = pasta / "rotulos_3.csv"
if arq_k.exists():
    kev = {r["nome_arquivo"]: r["rotulo"].strip() for r in csv.DictReader(open(arq_k, encoding="utf-8"))}
    nomes = sorted({q for v in por_foto.values() for q in v})
    for q in nomes:
        fotos = [n for n in sorted(por_foto) if q in por_foto[n] and n in kev]
        relatorio([(kev[n], por_foto[n][q]) for n in fotos], f"Kevin x {q}")
