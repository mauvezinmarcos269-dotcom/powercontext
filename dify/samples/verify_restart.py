"""Read-only snapshots around an operator-controlled PowerContext restart.

Run --phase before, stop the managed memory service, run --phase outage,
restart it with the same data directory, then run --phase after.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_service import load_env


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["before", "outage", "after"], required=True)
    phase = p.parse_args().phase
    load_env(ROOT / ".env")
    bridge = json.loads((ROOT / "evidence/bridge-run.json").read_text(encoding="utf-8"))
    path = ROOT / "evidence/restart-and-outage.json"
    evidence = {} if phase == "before" else json.loads(path.read_text(encoding="utf-8"))
    c = httpx.Client(timeout=40, trust_env=False, headers={"Authorization": "Bearer " + os.environ["SHOP_API_KEY"]})
    response = c.post("http://127.0.0.1:8012/turn/prepare", json={"player": bridge["player"], "operation_id": str(uuid.uuid4()), "action": "look", "detail": "看看"})
    if phase == "outage":
        assert response.status_code == 503
        evidence[phase] = {"status": response.status_code, "detail": response.json()["detail"], "passed": True}
    else:
        response.raise_for_status()
        data = response.json()
        evidence[phase] = {"status": response.status_code, "state": data["prior_state"], "memory_id": data["recalled_memory_id"]}
        if phase == "after":
            assert evidence["before"] == evidence["after"], "Persisted state changed across memory service restart"
            evidence["recovered_identical_state"] = True
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS", phase)


if __name__ == "__main__":
    main()
