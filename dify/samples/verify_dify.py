"""Run the complete game THROUGH Dify's published Chatflow (SSE API).

Every turn intentionally starts a NEW Dify conversation, retaining API user.
Run after import_dify.py. Saves responses + projected node traces, never secrets.
"""
import json
from pathlib import Path
import re
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    access = json.loads((ROOT / ".runtime/dify-access.json").read_text(encoding="utf-8"))
    run = uuid.uuid4().hex[:10]
    evidence = {"run": run, "transport": "Dify /v1/chat-messages streaming", "turns": [], "checks": []}
    c = httpx.Client(base_url=access["base_url"], timeout=240, trust_env=False,
                     headers={"Authorization": "Bearer " + access["app_api_key"]})

    def check(name, condition):
        assert condition, name
        evidence["checks"].append({"name": name, "passed": True})
        print("PASS", name, flush=True)

    def turn(query, user):
        answer, nodes, conversation, workflow = "", [], None, None
        with c.stream("POST", "/v1/chat-messages", json={"inputs": {}, "query": query,
            "response_mode": "streaming", "conversation_id": "", "user": user}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                kind, data = event.get("event"), event.get("data", {})
                if kind == "error":
                    raise RuntimeError("Dify execution failed: " + event.get("message", "unknown"))
                if kind == "workflow_finished" and data.get("status") != "succeeded":
                    raise RuntimeError("Workflow failed: " + str(data.get("error")))
                if kind == "workflow_started":
                    workflow = data.get("id")
                if kind == "node_finished":
                    nodes.append({k: data.get(k) for k in ("node_id", "node_type", "title", "status", "elapsed_time")})
                if kind in ("message", "agent_message"):
                    answer += event.get("answer", "")
                conversation = event.get("conversation_id") or conversation
        ids = re.findall(r"art_[a-zA-Z0-9]+", answer)
        record = {"query": query, "user": user, "conversation_id": conversation, "workflow_run_id": workflow,
                  "answer": answer, "memory_artifacts": ids, "nodes": nodes}
        evidence["turns"].append(record)
        # Save progress on each turn in case the next request fails.
        (ROOT / "evidence/dify-run.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        check("Dify completed all nine nodes: " + query, len(nodes) == 9 and all(n["status"] == "succeeded" for n in nodes))
        return record

    alice, bob = "dify-alice-" + run, "dify-bob-" + run
    first = turn("恶作剧 把招财猫换成尖叫鸡", alice)
    check("prank changes game state", "记仇 2/10" in first["answer"] and "11 店币" in first["answer"])
    second = turn("看看 老板你还记得我吗？", alice)
    check("distinct conversations", first["conversation_id"] != second["conversation_id"])
    check("cross-conversation recall uses previous memory", len(second["memory_artifacts"]) == 2 and second["memory_artifacts"][1] == first["memory_artifacts"][0])
    check("AI recalls the specific prank", "尖叫鸡" in second["answer"] or "招财猫" in second["answer"])
    turn("帮忙", alice)
    turn("送礼", alice)
    turn("送礼", alice)
    win = turn("买月亮", alice)
    check("complete playable ending", "结局已解锁" in win["answer"] and "记仇 0/10" in win["answer"] and "好感 5/10" in win["answer"])
    other = turn("看看", bob)
    check("Dify users have separate ledgers", "首次进店" in other["answer"] and "10 店币" in other["answer"] and "记仇 0/10" in other["answer"])
    reset = turn("重开", alice)
    check("reset restores initial game", "10 店币" in reset["answer"] and "记仇 0/10" in reset["answer"] and "好感 0/10" in reset["answer"])
    check("every turn persists real memory", all(t["memory_artifacts"] for t in evidence["turns"]))
    evidence["completed"] = True
    (ROOT / "evidence/dify-run.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Evidence:", ROOT / "evidence/dify-run.json")


if __name__ == "__main__":
    main()
