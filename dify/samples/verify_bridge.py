"""Real HTTP, real PowerContext and real model; writes only sanitized evidence."""
import json
from pathlib import Path
import sys
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_service import load_env
import os


def main():
    load_env(ROOT / ".env")
    run = uuid.uuid4().hex[:12]
    c = httpx.Client(base_url="http://127.0.0.1:8012", timeout=180, trust_env=False,
                     headers={"Authorization": "Bearer " + os.environ["SHOP_API_KEY"]})
    player = "bridge-alice-" + run
    checks, turns = [], []

    def check(name, ok):
        assert ok, name
        checks.append({"name": name, "passed": True})
        print("PASS", name, flush=True)

    def prepare(action, detail):
        r = c.post("/turn/prepare", json={"player": player, "operation_id": str(uuid.uuid4()), "action": action, "detail": detail})
        r.raise_for_status()
        return r.json()

    def complete(p):
        r = c.post("/turn/narrate", json={"ticket": p["ticket"]})
        r.raise_for_status()
        n = r.json()
        data = {"ticket": p["ticket"], "narration": n["narration"], "narration_proof": n["narration_proof"]}
        r = c.post("/turn/commit", json=data)
        r.raise_for_status()
        result = r.json()
        turns.append({"prior_state": p["prior_state"], "result": result, "model": n["model"], "usage": n.get("usage", {})})
        return data, result

    check("API key required", httpx.post("http://127.0.0.1:8012/turn/prepare", json={}, trust_env=False).status_code == 401)
    p = prepare("prank", "恶作剧 把招财猫换成尖叫鸡")
    check("new player starts empty", p["prior_state"]["seq"] == 0 and p["recalled_memory_id"] is None)
    data, first = complete(p)
    check("prank persisted to PowerContext", first["state"]["grudge"] == 2 and first["memory_id"].startswith("art_"))
    retry = c.post("/turn/commit", json=data).json()
    check("commit retry is idempotent", retry["state"]["seq"] == 1 and retry["memory_id"] == first["memory_id"])
    p2 = prepare("look", "看看 老板你还记得我吗？")
    check("fresh request recalls actual artifact", p2["recalled_memory_id"] == first["memory_id"] and "尖叫鸡" in p2["prior_state"]["signature_prank"])
    _, second = complete(p2)
    check("recalled memory reaches AI narration", "尖叫鸡" in second["narration"] or "招财猫" in second["narration"])
    b = c.post("/turn/prepare", json={"player": "bridge-bob-" + run, "operation_id": str(uuid.uuid4()), "action": "look", "detail": "看看"}).json()
    check("different players isolated", b["prior_state"]["seq"] == 0 and b["prior_state"]["pranks"] == 0 and b["prior_state"]["signature_prank"] == "")
    tampered = dict(data, narration="伪造台词")
    check("narration cannot be replaced before commit", c.post("/turn/commit", json=tampered).status_code == 400)
    invalid = c.post("/turn/narrate", json={"ticket": "malformed.signature"})
    check("invalid ticket rejected", invalid.status_code == 400)
    path = ROOT / "evidence/bridge-run.json"
    path.write_text(json.dumps({"run": run, "player": player, "checks": checks, "turns": turns}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Evidence:", path)


if __name__ == "__main__":
    main()
