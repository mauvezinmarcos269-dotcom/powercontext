"""Generate local secrets once; never overwrites an existing .env."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    print("Existing .env preserved")
else:
    path.write_text("POWERCONTEXT_URL=http://127.0.0.1:8011\nSHOP_API_KEY=" + secrets.token_urlsafe(32)
                    + "\nSHOP_SIGNING_KEY=" + secrets.token_urlsafe(32)
                    + "\nSHOP_DATA_DIR=.runtime/shop\n", encoding="utf-8")
    print("Created private .env. Add model configuration or use run_service.py --model-env.")
