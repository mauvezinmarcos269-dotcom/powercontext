"""Launch in a terminal. Reuses a chosen local model file without copying keys."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_env(path, allowed=None):
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if allowed is None or key in allowed:
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("service", choices=["memory", "shop"])
    p.add_argument("--model-env", type=Path)
    args = p.parse_args()
    os.chdir(ROOT)
    if (ROOT / ".env").exists():
        load_env(ROOT / ".env")
    if args.model_env:
        load_env(args.model_env.resolve(), {"MINIMAX_API_KEY", "MINIMAX_MODEL", "MINIMAX_CHAT_URL"})
    if args.service == "memory":
        os.environ["POWERCONTEXT_HOME"] = str(ROOT / ".runtime/powercontext")
        exe = Path(sys.executable).parent / ("powercontext.exe" if os.name == "nt" else "powercontext")
        subprocess.run([str(exe), "server", "run", "--no-env-file", "--host", "127.0.0.1", "--port", "8011"], check=True)
    else:
        subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8012", "--workers", "1"], check=True)


if __name__ == "__main__":
    main()
