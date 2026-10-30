"""Check deliverable syntax and accidental local-secret inclusion before push."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
files = [p for p in ROOT.rglob("*") if p.is_file() and not any(
    part in {".runtime", ".venv", "__pycache__", ".pytest_cache"} for part in p.relative_to(ROOT).parts)
    and p.name != ".env"]
for path in files:
    if path.suffix == ".py":
        compile(path.read_bytes(), str(path), "exec")
doc = yaml.safe_load((ROOT / "dsl/grudge-shop.yml").read_text(encoding="utf-8"))
for node in doc["workflow"]["graph"]["nodes"]:
    if node["data"]["type"] == "code":
        compile(node["data"]["code"], node["id"], "exec")
secrets = []
if (ROOT / ".env").exists():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and any(k in line.split("=", 1)[0] for k in ("KEY", "TOKEN", "PASSWORD")):
            value = line.split("=", 1)[1].strip()
            if len(value) > 12:
                secrets.append(value.encode())
for path in files:
    raw = path.read_bytes()
    if any(secret in raw for secret in secrets):
        raise SystemExit("Local credential found in deliverable: " + str(path.relative_to(ROOT)))
assert all(v["value"].startswith("REPLACE_") for v in doc["workflow"]["environment_variables"] if v["value_type"] == "secret")
print(f"PASS Python + DSL code syntax, placeholder credentials, local-secret exclusion ({len(files)} files)")
