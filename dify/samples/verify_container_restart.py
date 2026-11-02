"""Verify actual PowerContext persistence across container recreation, via Dify.

Run only against the --with-app deployment associated with dify-access.json.
The selected project's memory/shop containers are recreated; volumes are kept.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    args = p.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", args.project):
        raise SystemExit("Invalid project name")
    deployment = ROOT / ".runtime" / ("dify" if args.project == "grudge-dify" else args.project)
    access = json.loads((ROOT / ".runtime/dify-access.json").read_text(encoding="utf-8"))
    manifest = json.loads((deployment / "grudge-deployment.json").read_text(encoding="utf-8"))
    if not manifest["with_app"] or not access["base_url"].endswith(":" + str(manifest["port"])):
        raise SystemExit("Selected deployment does not match local Dify access settings")
    command = ["docker", "compose", "-p", args.project]
    user = "container-recovery-" + uuid.uuid4().hex[:12]

    def ids():
        return subprocess.check_output(command + ["ps", "-q", "memory", "shop"], cwd=deployment, text=True).splitlines()

    def turn(query):
        answer, conversation = "", None
        with httpx.Client(timeout=240, trust_env=False) as client:
            with client.stream("POST", access["base_url"] + "/v1/chat-messages",
                headers={"Authorization": "Bearer " + access["app_api_key"]},
                json={"inputs": {}, "query": query, "user": user, "response_mode": "streaming", "conversation_id": ""}) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    e = json.loads(line[6:])
                    if e.get("event") == "error":
                        raise RuntimeError(e.get("message", "Dify error"))
                    if e.get("event") == "workflow_finished" and e["data"].get("status") != "succeeded":
                        raise RuntimeError(e["data"].get("error", "Workflow failed"))
                    if e.get("event") == "message":
                        answer += e.get("answer", "")
                    conversation = e.get("conversation_id") or conversation
        return {"query": query, "answer": answer, "conversation_id": conversation,
                "memory_artifacts": re.findall(r"art_[a-zA-Z0-9]+", answer)}

    before_ids = ids()
    before = turn("恶作剧 把招财猫换成尖叫鸡")
    assert before["memory_artifacts"]
    subprocess.run(command + ["up", "-d", "--no-deps", "--force-recreate", "--wait", "--wait-timeout", "240", "memory", "shop"], cwd=deployment, check=True)
    after_ids = ids()
    assert len(before_ids) == len(after_ids) == 2 and not set(before_ids) & set(after_ids)
    after = turn("看看 老板你还记得我吗？")
    assert before["conversation_id"] != after["conversation_id"]
    assert len(after["memory_artifacts"]) == 2 and after["memory_artifacts"][1] == before["memory_artifacts"][0]
    assert "记仇 2/10" in after["answer"] and ("尖叫鸡" in after["answer"] or "招财猫" in after["answer"])
    result = {"project": args.project, "before_container_ids": before_ids, "after_container_ids": after_ids,
        "before": before, "after": after, "passed": True,
        "verification": "Both application containers recreated; distinct Dify conversations reuse the exact saved PowerContext artifact"}
    (ROOT / "evidence/container-recreation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS both containers recreated; persisted artifact and specific prank recalled through Dify")


if __name__ == "__main__":
    main()
