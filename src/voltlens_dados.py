"""
Leitura dos dados que alimentam o painel VoltLens.

Usado pelo script que carrega o Supabase (scripts/supabase_carregar.py):

- lotes: cada pasta de data/readings/<lote>/ com readings.csv;
- sugestão VoltLens: as colunas do readings.csv;
- registro do leiturista (PDA): data/sheets/BaseExtracao_*.csv, pelo nome da foto;
- gabarito: data/readings/evaluation.csv (leituras conferidas à mão).
"""

import csv
import random
import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data"
TEST_SET = "imgs_raw_test"
STATUS = ("lido", "leitura_suspeita", "ilegivel", "sem_leitura")


@dataclass
class Lote:
    id: str
    readings_csv: Path
    fotos: Path
    recortes: Path

    @property
    def nome(self) -> str:
        return batch_label(self.id)


def sources(readings_dir: Path = DATA / "readings") -> list[Lote]:
    """Lotes com readings.csv, na ordem: lotes PSP por nome e as fotos de teste por último."""
    found = []
    for batch_dir in sorted(p for p in readings_dir.iterdir() if p.is_dir()):
        csv_path = batch_dir / "readings.csv"
        if not csv_path.is_file():
            continue
        name = batch_dir.name
        if name == TEST_SET:
            found.append(Lote(name, csv_path, DATA / TEST_SET, DATA / "crops_display_test"))
        else:
            found.append(Lote(name, csv_path, DATA / "raw_images" / name, DATA / "display_crops" / name))
    found.sort(key=lambda lote: lote.id == TEST_SET)
    return found


def batch_label(name: str) -> str:
    """PSP_EXTRATLEITIMPL_030726_0121 -> 'Lote 03/07/26 · 0121'."""
    if name == TEST_SET:
        return "Fotos de teste (WhatsApp)"
    parts = name.split("_")
    if len(parts) >= 4 and len(parts[2]) == 6:
        d = parts[2]
        return f"Lote {d[0:2]}/{d[2:4]}/{d[4:6]} · {parts[3]}"
    return name


def read_rows(lote: Lote) -> list[dict]:
    with lote.readings_csv.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_pda(sheets_dir: Path = DATA / "sheets") -> dict[str, dict]:
    """Nome da foto -> registro do leiturista: m (medidor), l (leitura digitada), n (nota)."""
    pda = {}
    if not sheets_dir.is_dir():
        return pda
    for path in sorted(sheets_dir.glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                photo = (row.get("Foto do medidor") or "").strip()
                if not photo or photo == "NA":
                    continue
                pda[photo] = {
                    "m": _clean(row.get("Numero do medidor")),
                    "l": _clean(row.get("Posicao do medidor lida")),
                    "n": _clean(row.get("Nota de Leitura Atual")),
                }
    return pda


def load_expected(path: Path = DATA / "readings" / "evaluation.csv") -> dict[str, str]:
    """Nome da foto -> leitura conferida à mão."""
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return {row["image"]: row["expected"] for row in csv.DictReader(f) if row.get("expected")}


def cmp_pda(reading: str | None, pda_reading: str | None) -> str:
    """'bate' se a leitura do OCR é o mesmo número digitado no PDA, 'diverge' se não, 'na' se falta um dos dois."""
    a, b = _digits(reading), _digits(pda_reading)
    if not a or not b:
        return "na"
    return "bate" if int(a) == int(b) else "diverge"


def num(v: str | None) -> float | None:
    return float(v) if v not in (None, "") else None


def sample_rows(rows: list[dict], size: int, expected: dict, seed: int) -> list[dict]:
    """Amostra estratificada por status, priorizando fotos com gabarito. size <= 0 devolve tudo."""
    if size <= 0 or len(rows) <= size:
        return rows
    rng = random.Random(seed)
    by_status: dict[str, list[dict]] = {}
    for row in rows:
        by_status.setdefault(row["status"], []).append(row)
    picked = []
    for group in by_status.values():
        share = max(1, round(size * len(group) / len(rows)))
        with_gab = [r for r in group if r["image"] in expected]
        without = [r for r in group if r["image"] not in expected]
        rng.shuffle(with_gab)
        rng.shuffle(without)
        picked += (with_gab + without)[:share]
    order = {id(r): i for i, r in enumerate(rows)}
    return sorted(picked[:size], key=lambda r: order[id(r)])


def _clean(v: str | None) -> str:
    v = (v or "").strip()
    return "" if v == "NA" else v


def _digits(v: str | None) -> str:
    return re.sub(r"\D", "", v or "")
