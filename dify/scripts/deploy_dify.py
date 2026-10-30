"""Prepare a private local Dify 1.9.1 deployment from official source.

Run from dify/: python scripts/deploy_dify.py --source /path/to/dify-1.9.1
No database/vector/model plugin is required by this app's HTTP-only Chatflow.
"""
import argparse
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.9.1"
SERVICES = ["api", "worker", "web", "db", "redis", "sandbox", "plugin_daemon", "ssrf_proxy", "nginx"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path)
    p.add_argument("--prepare-only", action="store_true")
    args = p.parse_args()
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    source = args.source or runtime / "dify-source"
    if not source.exists():
        subprocess.run(["git", "clone", "--depth", "1", "--branch", VERSION,
                        "--filter=blob:none", "--sparse", "https://github.com/langgenius/dify.git", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "sparse-checkout", "set", "docker"], check=True)
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != "cd47a47c3b4acc4d4457b73777722602c33bc950":
        raise SystemExit("Expected official Dify 1.9.1 commit cd47a47; refusing a different source")
    target = runtime / "dify"
    if not target.exists():
        shutil.copytree(source / "docker", target)
        data = yaml.safe_load((target / "docker-compose.yaml").read_text(encoding="utf-8"))
        data["services"] = {k: data["services"][k] for k in SERVICES}
        # No external database port. Only nginx is exposed on loopback.
        data["services"]["nginx"]["ports"] = ["127.0.0.1:18080:80"]
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
        (target / "docker-compose.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        # Allow only our bridge through the Dify HTTP proxy, keep other ACLs.
        squid = target / "ssrf_proxy/squid.conf.template"
        text = squid.read_text(encoding="utf-8")
        text = text.replace("http_access deny all", "acl grudge_bridge dstdomain host.docker.internal\nhttp_access allow grudge_bridge\nhttp_access deny all", 1)
        squid.write_text(text, encoding="utf-8", newline="\n")
        env = (target / ".env.example").read_text(encoding="utf-8")
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
        (target / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (runtime / "deployment-source.json").write_text(json.dumps({"dify": VERSION, "commit": revision,
            "upstream": "https://github.com/langgenius/dify", "services": SERVICES}, indent=2), encoding="utf-8")
    if not args.prepare_only:
        subprocess.run(["docker", "compose", "-p", "grudge-dify", "up", "-d"], cwd=target, check=True)
    print("Dify: http://localhost:18080 · private settings: .runtime/dify/.env")


if __name__ == "__main__":
    main()
