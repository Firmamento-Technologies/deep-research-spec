"""Config package - loads .env before settings instantiation."""

from pathlib import Path
import logging
from dotenv import load_dotenv

# CRITICAL: Load .env FIRST, before settings.py is imported anywhere
logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=True)
    logger.debug("Loaded .env from %s", ENV_FILE)
else:
    logger.warning(".env not found at %s", ENV_FILE)
