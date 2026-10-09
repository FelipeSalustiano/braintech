"""Gera rotulos/ids.csv (nome_arquivo, id_leitura, numero_medidor) a partir dos CSVs do cliente.

Uso: python gerar_ids.py --zip "<Base de Dados Neoenergia PE.zip>"      (ou --csvs <pasta com os 4 CSVs>)
Chave: nome da foto == coluna 'Foto do medidor' do CSV. Foto sem registro (órfã) recebe um
numero_medidor fictício único (SEM_REGISTRO_<id_leitura>), para a prova de vazamento do notebook (C4)
não contar essas fotos como "o mesmo medidor". O ids.csv tem números de medidor do cliente: não versionar.
"""
import argparse, io, re, zipfile
from pathlib import Path
import pandas as pd

ap = argparse.ArgumentParser()
g = ap.add_mutually_exclusive_group(required=True)
g.add_argument("--zip")
g.add_argument("--csvs")
a = ap.parse_args()
RAIZ = Path(__file__).resolve().parent.parent

fontes = []
if a.zip:
    z = zipfile.ZipFile(a.zip)
    fontes = [io.BytesIO(z.read(i)) for i in z.infolist() if i.filename.endswith(".csv")]
else:
    fontes = list(Path(a.csvs).rglob("*.csv"))
reg = pd.concat([pd.read_csv(f, sep=None, engine="python", dtype=str) for f in fontes], ignore_index=True)
reg.columns = ["medidor", "posicao", "nota", "foto"]
reg = reg.dropna(subset=["foto"]).drop_duplicates("foto")

rot = pd.read_csv(RAIZ / "rotulos" / "rotulos.csv")
m = rot[["nome_arquivo"]].merge(reg[["foto", "medidor"]], left_on="nome_arquivo", right_on="foto", how="left")
m["id_leitura"] = m.nome_arquivo.str.replace(r"_\d{3}\.jpg$", "", regex=True)
orfas = m.medidor.isna()
m.loc[orfas, "medidor"] = "SEM_REGISTRO_" + m.loc[orfas, "id_leitura"]
m.rename(columns={"medidor": "numero_medidor"})[["nome_arquivo", "id_leitura", "numero_medidor"]].to_csv(RAIZ / "rotulos" / "ids.csv", index=False)
print(f"ids.csv: {len(m)} fotos | {m.id_leitura.nunique()} leituras | órfãs (sem registro): {orfas.sum()}")
