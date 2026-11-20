"""
Cliente mínimo das APIs REST do Supabase (banco, Storage e Auth admin) para os scripts.

Usa só a biblioteca padrão, para não depender da versão do pacote supabase-py.
Lê SUPABASE_URL e SUPABASE_SECRET_KEY do ambiente ou do arquivo .env da raiz.
Aceita tanto a chave nova (sb_secret_...) quanto a antiga (service_role, um JWT).
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    """Carrega KEY=VALUE do .env sem sobrescrever o que já está no ambiente."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class SupabaseError(RuntimeError):
    pass


class Supabase:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key

    @classmethod
    def from_env(cls) -> "Supabase":
        load_dotenv()
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SECRET_KEY")
        if not url or not key:
            raise SystemExit("Faltam SUPABASE_URL e/ou SUPABASE_SECRET_KEY no .env da raiz (veja .env.example).")
        return cls(url, key)

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {"apikey": self.key}
        if not self.key.startswith("sb_"):  # chave antiga (JWT) também vai no Authorization
            headers["Authorization"] = f"Bearer {self.key}"
        headers.update(extra or {})
        return headers

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        req = urllib.request.Request(self.url + path, data=body, method=method, headers=self._headers(headers))
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise SupabaseError(f"{method} {path} -> {e.code}: {e.read().decode('utf-8', 'replace')[:500]}") from None
        return json.loads(raw) if raw else None

    # ---------- banco (PostgREST)
    def upsert(self, table: str, rows: list[dict], on_conflict: str) -> None:
        self.request("POST", f"/rest/v1/{table}?on_conflict={on_conflict}", json.dumps(rows).encode("utf-8"),
                     {"Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"})

    # ---------- Storage
    def upload(self, bucket: str, path: str, body: bytes, content_type: str) -> None:
        quoted = urllib.parse.quote(path)
        self.request("POST", f"/storage/v1/object/{bucket}/{quoted}", body,
                     {"Content-Type": content_type, "x-upsert": "true", "Cache-Control": "max-age=31536000"})

    def download(self, bucket: str, path: str) -> bytes:
        req = urllib.request.Request(f"{self.url}/storage/v1/object/{bucket}/{urllib.parse.quote(path)}",
                                     headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            raise SupabaseError(f"GET {path} -> {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None

    def list_objects(self, bucket: str, prefix: str) -> set[str]:
        """Caminhos completos de todos os arquivos abaixo de prefix (percorre as subpastas)."""
        found, pending = set(), [prefix.strip("/")]
        while pending:
            folder = pending.pop()
            offset = 0
            while True:
                page = self.request("POST", f"/storage/v1/object/list/{bucket}",
                                    json.dumps({"prefix": folder, "limit": 1000, "offset": offset}).encode("utf-8"),
                                    {"Content-Type": "application/json"}) or []
                for obj in page:
                    full = f"{folder}/{obj['name']}" if folder else obj["name"]
                    if obj.get("id") is None:  # pasta
                        pending.append(full)
                    else:
                        found.add(full)
                if len(page) < 1000:
                    break
                offset += 1000
        return found

    def delete_objects(self, bucket: str, paths: list[str]) -> None:
        for start in range(0, len(paths), 1000):
            self.request("DELETE", f"/storage/v1/object/{bucket}",
                         json.dumps({"prefixes": paths[start:start + 1000]}).encode("utf-8"),
                         {"Content-Type": "application/json"})

    # ---------- banco: apagar linhas (o PostgREST exige um filtro; "col=not.is.null" pega todas)
    def delete_all(self, table: str, column: str) -> None:
        self.request("DELETE", f"/rest/v1/{table}?{column}=not.is.null", headers={"Prefer": "return=minimal"})

    def count(self, table: str) -> int:
        req = urllib.request.Request(f"{self.url}/rest/v1/{table}?select=*", method="HEAD",
                                     headers=self._headers({"Prefer": "count=exact"}))
        with urllib.request.urlopen(req, timeout=60) as resp:
            return int(resp.headers.get("Content-Range", "*/0").split("/")[-1])

    # ---------- Auth (admin)
    def create_user(self, email: str, password: str, metadata: dict) -> dict:
        body = {"email": email, "password": password, "email_confirm": True, "user_metadata": metadata}
        return self.request("POST", "/auth/v1/admin/users", json.dumps(body).encode("utf-8"),
                            {"Content-Type": "application/json"})

    def list_users(self) -> list[dict]:
        users, page = [], 1
        while True:
            batch = (self.request("GET", f"/auth/v1/admin/users?page={page}&per_page=1000") or {}).get("users", [])
            users += batch
            if len(batch) < 1000:
                return users
            page += 1

    def delete_user(self, user_id: str) -> None:
        self.request("DELETE", f"/auth/v1/admin/users/{user_id}")
