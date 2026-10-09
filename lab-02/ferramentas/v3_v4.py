"""V3 (pareamento foto <-> registro) e V4 (as leituras de valor 0 como teste difícil).

Uso: python v3_v4.py --zip "<Base de Dados Neoenergia PE.zip>" --fotos <FOTOS_DIR do notebook>
As fotos são lidas direto do zip (nada é extraído para o repositório). Saída: texto no terminal e
lab-02/saidas/zeros_predicoes.csv (ignorado pelo git).
"""
import argparse, io, re, zipfile
from pathlib import Path
import numpy as np, pandas as pd, torch, torch.nn as nn, torch.nn.functional as F
from PIL import Image
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

ap = argparse.ArgumentParser()
ap.add_argument("--zip", required=True)
ap.add_argument("--fotos", required=True)
a = ap.parse_args()
RAIZ = Path(__file__).resolve().parent.parent
CLASSES = ["legivel", "ilegivel", "nao_medidor"]
TREINO = ["PSP_EXTRATLEITIMPL_200526_0352", "PSP_EXTRATLEITIMPL_210526_0335"]
VAL = ["PSP_EXTRATLEITIMPL_220526_0408"]
MEDIA, DP = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1), torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
base = lambda s: re.sub(r"_\d{3}\.jpg$", "", s)

# ---------------- V3: pareamento ----------------
z = zipfile.ZipFile(a.zip)
jpgs, regs = {}, []
for i in z.infolist():
    p = i.filename.split("/")
    if len(p) < 3 or not p[-1]:
        continue
    if p[-1].lower().endswith(".jpg"):
        jpgs[p[-1]] = (p[1], i)
    elif p[-1].endswith(".csv"):
        d = pd.read_csv(io.BytesIO(z.read(i)), sep=None, engine="python", dtype=str)
        d.columns = ["medidor", "posicao", "nota", "foto"]
        d["lote"] = p[1]
        regs.append(d)
reg = pd.concat(regs, ignore_index=True)
com_foto = reg[reg.foto.notna()]
orfas = sorted(set(jpgs) - set(com_foto.foto))
print("== V3: regra = nome do arquivo == coluna 'Foto do medidor' do CSV (casamento exato) ==")
print(f"jpgs: {len(jpgs)} | registros: {len(reg)} | registros com foto: {len(com_foto)} | sem foto: {len(reg) - len(com_foto)}")
print(f"registros cuja foto não existe no zip: {len(set(com_foto.foto) - set(jpgs))} | nomes duplicados no CSV: {com_foto.foto.duplicated().sum()}")
print(f"fotos órfãs (jpg sem registro): {len(orfas)} = {len(orfas) / len(jpgs):.1%}")
print(pd.Series([jpgs[o][0] for o in orfas]).value_counts().sort_index().to_string())
print("órfãs por sufixo:", pd.Series([re.search(r"_(\d{3})\.jpg$", o).group(1) for o in orfas]).value_counts().sort_index().to_dict())
print("órfãs cujo id de leitura (sem sufixo) existe no CSV:", sum(base(o) in {base(f) for f in com_foto.foto} for o in orfas))

# ---------------- V4: zeros ----------------
reg["zero"] = reg.posicao.astype(str).str.strip() == "0"
print(f"\n== V4: leituras com valor 0: {reg.zero.sum()} | com foto: {(reg.zero & reg.foto.notna()).sum()} ==")
rot = set(pd.read_csv(RAIZ / "rotulos" / "rotulos.csv").nome_arquivo)
z0 = reg[reg.zero & reg.foto.notna()]
z0 = z0[~z0.foto.isin(rot)].reset_index(drop=True)      # fora das 300 rotuladas (não contaminar)
print(f"zeros com foto fora das 300 rotuladas: {len(z0)}")


def tensor(img):
    t = torch.from_numpy(np.asarray(img.convert("RGB")).copy()).permute(2, 0, 1).float() / 255
    return (t - MEDIA) / DP


def do_zip(nome):
    return tensor(Image.open(io.BytesIO(z.read(jpgs[nome][1]))))


torch.manual_seed(0)
np.random.seed(0)
ext = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1).features.eval()
pool = nn.AdaptiveAvgPool2d(1)


@torch.no_grad()
def feats(X):
    return torch.cat([pool(ext(X[i:i + 32])).flatten(1) for i in range(0, len(X), 32)])


rot_df = pd.read_csv(RAIZ / "rotulos" / "rotulos.csv")
def carrega(sub):
    X = torch.stack([tensor(Image.open(Path(a.fotos) / r.lote / r.nome_arquivo)) for r in sub.itertuples()])
    return feats(X), torch.tensor([CLASSES.index(r) for r in sub.rotulo])
Ftr, ytr = carrega(rot_df[rot_df.lote.isin(TREINO)])
Fva, yva = carrega(rot_df[rot_df.lote.isin(VAL)])
# mesma cabeça do notebook (D3/E): semente 0, minibatches, T ajustado na validação
g = torch.Generator().manual_seed(0)
cab = nn.Linear(576, 3)
opt = torch.optim.AdamW(cab.parameters(), lr=1e-3, weight_decay=1e-3)
peso = (len(ytr) / (3 * torch.bincount(ytr, minlength=3).clamp(min=1))).float()
for _ in range(30):
    for idx in torch.randperm(len(ytr), generator=g).split(16):
        opt.zero_grad(); F.cross_entropy(cab(Ftr[idx]), ytr[idx], weight=peso).backward(); opt.step()
T = torch.ones(1, requires_grad=True)
with torch.no_grad(): Lva = cab(Fva)
o = torch.optim.LBFGS([T], lr=0.1, max_iter=100)
def clos():
    o.zero_grad(); l = F.cross_entropy(Lva / T, yva); l.backward(); return l
o.step(clos); T = T.item()
print(f"cabeça treinada em {len(ytr)} fotos (20/05+21/05), T = {T:.3f}")


def prever(nomes):
    X = torch.stack([do_zip(n) for n in nomes])
    with torch.no_grad(): p = (cab(feats(X)) / T).softmax(1)
    return p


def resumo(nome, df, p):
    conf, pred = p.max(1)
    print(f"\n{nome} (n={len(df)})")
    for k, c in enumerate(CLASSES):
        print(f"  {c:<12} {(pred == k).sum().item():>4}  ({(pred == k).float().mean():.1%})")
    print(f"  confiança média {conf.mean():.2f} | legível com confiança >= 0,7: {((pred == 0) & (conf >= 0.7)).sum().item()}")
    return pred, conf


p0 = prever(z0.foto.tolist())
pred0, conf0 = resumo("ZEROS com foto", z0, p0)
# comparação: leituras NÃO zero (e não 99999), mesma quantidade, fora das rotuladas
cmp_ = com_foto[(com_foto.posicao.astype(str).str.strip() != "0") & ~com_foto.foto.isin(rot)]
cmp_ = cmp_.sample(len(z0), random_state=0).reset_index(drop=True)
p1 = prever(cmp_.foto.tolist())
resumo("CONTROLE: leituras de valor != 0, amostra do mesmo tamanho", cmp_, p1)

out = RAIZ / "saidas"
out.mkdir(exist_ok=True)
z0.assign(pred=[CLASSES[i] for i in pred0.tolist()], conf=conf0.numpy().round(3)).to_csv(out / "zeros_predicoes.csv", index=False)
print("\nzeros legíveis por lote:")
print(pd.crosstab(z0.lote, pd.Series([CLASSES[i] for i in pred0.tolist()], name="pred")).to_string())
print("zeros legíveis por nota de leitura (top):")
print(pd.crosstab(z0.nota.fillna("(sem nota)"), pd.Series([CLASSES[i] for i in pred0.tolist()], name="pred").values).sort_values("legivel", ascending=False).head(6).to_string())
