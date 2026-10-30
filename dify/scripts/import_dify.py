"""Initialize this private local instance, import DSL, and publish the Chatflow.

Uses Dify 1.9.1 console API. Credentials remain under ignored .runtime/.
Refuses to initialize an existing unrelated instance without known credentials.
"""
import argparse
import json
from pathlib import Path
import secrets
import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:18080")
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    path = ROOT / ".runtime/dify-access.json"
    credentials = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    client = httpx.Client(base_url=base + "/console/api", timeout=120, trust_env=False)

    def call(method, route, **kwargs):
        r = client.request(method, route, **kwargs)
        if not r.is_success:
            # Errors may contain request data: do not print request/DSL/keys.
            try:
                message = r.json().get("message", "")
            except ValueError:
                message = "non-JSON response"
            raise RuntimeError(f"Dify {method} {route}: HTTP {r.status_code}: {message}")
        return r.json()

    status = call("GET", "/setup")
    if status["step"] == "not_started":
        if credentials is None:
            credentials = {"email": "judge@grudge-shop.local", "password": "Shop9" + secrets.token_urlsafe(24)}
            path.write_text(json.dumps(credentials, indent=2), encoding="utf-8")
        call("POST", "/setup", json={"email": credentials["email"], "name": "Grudge Shop", "password": credentials["password"]})
        print("Initialized independent local Dify instance")
    if credentials is None:
        raise SystemExit("Existing instance: supply your own local .runtime/dify-access.json; nothing was changed")
    login = call("POST", "/login", json={"email": credentials["email"], "password": credentials["password"]})
    client.headers["Authorization"] = "Bearer " + login["data"]["access_token"]
    doc = yaml.safe_load((ROOT / "dsl/grudge-shop.yml").read_text(encoding="utf-8"))
    env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if "=" in l and not l.startswith("#"))
    for variable in doc["workflow"]["environment_variables"]:
        if variable["name"] == "SHOP_API_KEY":
            variable["value"] = env["SHOP_API_KEY"]
    body = {"mode": "yaml-content", "yaml_content": yaml.safe_dump(doc, allow_unicode=True), "name": "记仇杂货铺"}
    if credentials.get("app_id"):
        body["app_id"] = credentials["app_id"]
    result = call("POST", "/apps/imports", json=body)
    if result["status"] == "pending":
        result = call("POST", "/apps/imports/" + result["id"] + "/confirm", json={})
    if result["status"] not in ("completed", "completed-with-warnings"):
        raise RuntimeError("Unexpected import status: " + result["status"])
    app_id = result["app_id"]
    credentials["app_id"] = app_id
    path.write_text(json.dumps(credentials, indent=2), encoding="utf-8")
    print("DSL imported:", app_id, result["status"])
    call("POST", f"/apps/{app_id}/workflows/publish", json={"marked_name": "competition-v1", "marked_comment": "Dify + real PowerContext + MiniMax"})
    call("POST", f"/apps/{app_id}/site", json={"title": "记仇杂货铺", "default_language": "zh-Hans", "chat_color_theme": "#B45309", "show_workflow_steps": True})
    detail = call("GET", f"/apps/{app_id}")
    keys = call("GET", f"/apps/{app_id}/api-keys")["data"]
    key = keys[0]["token"] if keys else call("POST", f"/apps/{app_id}/api-keys", json={})["token"]
    credentials.update({"app_api_key": key, "base_url": base,
                        "chat_url": base + "/chat/" + detail["site"]["code"]})
    path.write_text(json.dumps(credentials, indent=2), encoding="utf-8")
    evidence = {"dify_version": "1.9.1", "dsl_version": doc["version"], "status": result["status"],
        "app_id": app_id, "chat_url": credentials["chat_url"], "node_count": len(doc["workflow"]["graph"]["nodes"]),
        "dependencies": doc["dependencies"], "published": True}
    (ROOT / "evidence/dify-import.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Chat:", credentials["chat_url"])
    print("Private local admin login and API key:", path)


if __name__ == "__main__":
    main()
