"""Bounded service readiness checks; no credentials are logged."""
import time
import httpx


def wait_json(url, timeout=180, predicate=lambda data: True):
    deadline = time.monotonic() + timeout
    last = "not attempted"
    with httpx.Client(trust_env=False, timeout=5) as client:
        while time.monotonic() < deadline:
            try:
                r = client.get(url)
                last = f"HTTP {r.status_code}"
                if r.is_success and predicate(r.json()):
                    return r.json()
            except (httpx.HTTPError, ValueError) as exc:
                last = type(exc).__name__
            time.sleep(1)
    raise RuntimeError(f"Service did not become ready within {timeout}s: {url} ({last})")
