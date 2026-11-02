"""Prepare a private local Dify 1.9.1 deployment from official source.

Run from dify/: python scripts/deploy_dify.py --source /path/to/dify-1.9.1
No database/vector/model plugin is required by this app's HTTP-only Chatflow.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import yaml
from readiness import wait_json
from run_service import load_env

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.9.1"
SERVICES = ["api", "worker", "web", "db", "redis", "sandbox", "plugin_daemon", "ssrf_proxy", "nginx"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path)
    p.add_argument("--prepare-only", action="store_true")
    p.add_argument("--with-app", action="store_true", help="Run real PowerContext and shop in the same Docker network")
    p.add_argument("--model-env", type=Path, help="Read local MiniMax settings without copying credentials into source")
    p.add_argument("--project", default="grudge-dify")
    p.add_argument("--port", type=int, default=18080)
    p.add_argument("--wait-timeout", type=int, default=240)
    args = p.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", args.project) or not 1024 <= args.port <= 65535:
        raise SystemExit("Use a simple lowercase Compose project and a port between 1024 and 65535")
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    if (ROOT / ".env").exists():
        load_env(ROOT / ".env")
    if args.model_env:
        load_env(args.model_env.resolve(), {"MINIMAX_API_KEY", "MINIMAX_MODEL", "MINIMAX_CHAT_URL"})
    if args.with_app:
        for key in ["SHOP_API_KEY", "SHOP_SIGNING_KEY", "MINIMAX_API_KEY"]:
            value = os.getenv(key, "")
            if len(value) < 24 or value.startswith(("REPLACE_", "YOUR_")):
                raise SystemExit(f"Configure {key} before deploying --with-app; credential values are never printed")
    source = (args.source or runtime / "dify-source").resolve()
    if source.exists() and not (source / ".git").exists():
        raise SystemExit(f"Incomplete source checkout: {source}. Restore or move it aside, then rerun")
    if not source.exists():
        subprocess.run(["git", "clone", "--depth", "1", "--branch", VERSION,
                        "--filter=blob:none", "--sparse", "https://github.com/langgenius/dify.git", str(source)], check=True)
    # A previous clone can succeed while sparse checkout fails: retry the missing step.
    if not (source / "docker/docker-compose.yaml").exists():
        subprocess.run(["git", "-C", str(source), "sparse-checkout", "add", "docker"], check=True)
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != "cd47a47c3b4acc4d4457b73777722602c33bc950":
        raise SystemExit("Expected official Dify 1.9.1 commit cd47a47; refusing a different source")
    target = runtime / ("dify" if args.project == "grudge-dify" else args.project)
    if not target.exists() and not args.prepare_only:
        volumes = subprocess.check_output(["docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={args.project}"], text=True)
        if volumes.strip():
            raise SystemExit("This project already has Docker volumes from another deployment directory. Use a new --project and --port to preserve the original database credentials")
    manifest = target / "grudge-deployment.json"
    if target.exists():
        if not manifest.exists():
            raise SystemExit("Existing deployment has no manifest. Use a new --project and --port; existing data is preserved")
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous != {"with_app": args.with_app, "port": args.port}:
            raise SystemExit("Deployment options changed. Use a new --project/--port instead of reusing existing volumes")
    if not target.exists():
        # Build completely in a staging directory: failed preparation is never treated as ready.
        staging = target.with_name(target.name + ".preparing-" + secrets.token_hex(4))
        shutil.copytree(source / "docker", staging)
        data = yaml.safe_load((staging / "docker-compose.yaml").read_text(encoding="utf-8"))
        data["services"] = {k: data["services"][k] for k in SERVICES}
        # No external database port. Only nginx is exposed on loopback.
        data["services"]["nginx"]["ports"] = [f"127.0.0.1:{args.port}:80"]
        data["services"]["plugin_daemon"].pop("ports", None)
        # Named volumes avoid Windows host filesystem permission differences.
        data.setdefault("volumes", {})
        for service, old_mount, name in [
            ("api", "./volumes/app/storage:/app/api/storage", "app_storage"),
            ("worker", "./volumes/app/storage:/app/api/storage", "app_storage"),
            ("db", "./volumes/db/data:/var/lib/postgresql/data", "postgres_data"),
            ("redis", "./volumes/redis/data:/data", "redis_data"),
            ("plugin_daemon", "./volumes/plugin_daemon:/app/storage", "plugin_data")]:
            svc = data["services"][service]
            svc["volumes"] = [name + ":" + m.split(":", 1)[1] if m == old_mount else m for m in svc["volumes"]]
            data["volumes"][name] = {}
        # Linux Docker does not automatically provide Docker Desktop's host alias.
        data["services"]["ssrf_proxy"]["extra_hosts"] = ["host.docker.internal:host-gateway"]
        if args.with_app:
            image = f"{args.project}-shop:1"
            memory_token = secrets.token_urlsafe(32)
            (staging / "memory.env").write_text("POWERCONTEXT_SERVER_AUTH_TOKEN=" + memory_token + "\n", encoding="utf-8")
            data["services"]["memory"] = {
                "image": image, "build": {"context": str(ROOT), "dockerfile": "deploy/Dockerfile"},
                "command": ["powercontext", "server", "run", "--no-env-file", "--host", "0.0.0.0", "--port", "8011"],
                "env_file": ["memory.env"],
                "environment": {"POWERCONTEXT_HOME": "/data/powercontext", "POWERCONTEXT_SERVER_AUTH_ENABLED": "true"},
                "volumes": ["memory_data:/data/powercontext"], "restart": "unless-stopped",
                "healthcheck": {"test": ["CMD", "python", "-c", "import urllib.request,os; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8011/v1/server-info',headers={'Authorization':'Bearer '+os.environ['POWERCONTEXT_SERVER_AUTH_TOKEN']}),timeout=3)"],
                    "interval": "3s", "timeout": "5s", "retries": 60, "start_period": "15s"}}
            data["services"]["shop"] = {
                "image": image, "build": {"context": str(ROOT), "dockerfile": "deploy/Dockerfile"},
                "env_file": ["app.env"], "environment": {"POWERCONTEXT_URL": "http://memory:8011", "SHOP_DATA_DIR": "/data/shop"},
                "volumes": ["shop_data:/data/shop"], "restart": "unless-stopped",
                "depends_on": {"memory": {"condition": "service_healthy"}},
                "healthcheck": {"test": ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8012/ready',timeout=3)"],
                    "interval": "3s", "timeout": "5s", "retries": 40, "start_period": "5s"}}
            data["volumes"].update({"memory_data": {}, "shop_data": {}})
            app_env = {key: os.environ[key] for key in ["SHOP_API_KEY", "SHOP_SIGNING_KEY", "MINIMAX_API_KEY"]}
            app_env["POWERCONTEXT_TOKEN"] = memory_token
            app_env.update({"MINIMAX_MODEL": os.getenv("MINIMAX_MODEL", "MiniMax-M2.5"),
                "MINIMAX_CHAT_URL": os.getenv("MINIMAX_CHAT_URL", "https://api.minimaxi.com/v1/text/chatcompletion_v2")})
            if any("\n" in value or "\r" in value for value in app_env.values()):
                raise SystemExit("Environment values must each occupy one line")
            # Compose single quotes disable interpolation (including $ in credentials).
            (staging / "app.env").write_text("\n".join(k + "='" + v.replace("'", "\\'") + "'" for k, v in app_env.items()) + "\n", encoding="utf-8")
        (staging / "docker-compose.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        # Allow only our bridge through the Dify HTTP proxy, keep other ACLs.
        squid = staging / "ssrf_proxy/squid.conf.template"
        text = squid.read_text(encoding="utf-8")
        domain = "shop" if args.with_app else "host.docker.internal"
        text = text.replace("http_access deny all", f"acl grudge_bridge dstdomain {domain}\nhttp_access allow grudge_bridge\nhttp_access deny all", 1)
        squid.write_text(text, encoding="utf-8", newline="\n")
        env = (staging / ".env.example").read_text(encoding="utf-8")
        replacements = {"SECRET_KEY": secrets.token_urlsafe(42), "DB_PASSWORD": secrets.token_urlsafe(24),
            "REDIS_PASSWORD": secrets.token_urlsafe(24), "CODE_EXECUTION_API_KEY": secrets.token_urlsafe(32),
            "SANDBOX_API_KEY": secrets.token_urlsafe(32), "PLUGIN_DAEMON_KEY": secrets.token_urlsafe(32),
            "PLUGIN_DIFY_INNER_API_KEY": secrets.token_urlsafe(32), "EXPOSE_NGINX_PORT": "18080",
            "EXPOSE_NGINX_SSL_PORT": "18443", "EXPOSE_PLUGIN_DEBUGGING_PORT": "15003",
            "PM2_INSTANCES": "1", "NEXT_TELEMETRY_DISABLED": "1"}
        # sandbox and API must use the same execution key (official SANDBOX_API_KEY).
        replacements["CODE_EXECUTION_API_KEY"] = replacements["SANDBOX_API_KEY"]
        lines = []
        for line in env.splitlines():
            key = line.split("=", 1)[0]
            if key in replacements:
                line = key + "=" + replacements.pop(key)
            lines.append(line)
        lines += [k + "=" + v for k, v in replacements.items()]
        (staging / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (staging / "grudge-deployment.json").write_text(json.dumps({"with_app": args.with_app, "port": args.port}), encoding="utf-8")
        staging.rename(target)
        (runtime / "deployment-source.json").write_text(json.dumps({"dify": VERSION, "commit": revision,
            "upstream": "https://github.com/langgenius/dify", "services": SERVICES}, indent=2), encoding="utf-8")
    if not args.prepare_only:
        subprocess.run(["docker", "compose", "--progress", "plain", "-p", args.project, "up", "-d", "--build", "--wait", "--wait-timeout", str(args.wait_timeout)], cwd=target, check=True)
        wait_json(f"http://127.0.0.1:{args.port}/console/api/setup", args.wait_timeout,
                  lambda data: data.get("step") in ("finished", "not_started"))
    print(f"Dify: http://localhost:{args.port} · deployment directory: {target}")
    if args.with_app:
        print("Import using --shop-base-url http://shop:8012 (real PowerContext + shop are container services)")


if __name__ == "__main__":
    main()
