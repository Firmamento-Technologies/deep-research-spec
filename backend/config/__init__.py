"""Config package - loads .env before settings instantiation."""

from pathlib import Path
from dotenv import load_dotenv

# CRITICAL: Load .env FIRST, before settings.py is imported anywhere
BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=True)
    print(f"[Config.__init__] Loaded .env from: {ENV_FILE}")
else:
    print(f"[Config.__init__] WARNING: .env not found at {ENV_FILE}")
