"""Configuration, read from the environment (.env) so nothing is hard-coded."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # A random key is fine locally; set SECRET_KEY to keep sessions across restarts.
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    DATABASE_PATH = os.environ.get("DATABASE_PATH") or str(BASE_DIR / "tracker.db")
    # The pre-rebuild database; its saved searches are imported once.
    LEGACY_DATABASE_PATH = os.environ.get("LEGACY_DATABASE_PATH") or str(BASE_DIR / "_old" / "tracker.db")
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "5000"))
    DEBUG = _flag("FLASK_DEBUG", False)
    # Store search. Blank BROWSER_CHANNEL = Playwright's own Chromium, else Edge, else Chrome.
    BROWSER_CHANNEL = os.environ.get("BROWSER_CHANNEL", "")
    # 0 shows the browser window while it works: useful when a store starts blocking.
    BROWSER_HEADLESS = _flag("BROWSER_HEADLESS", True)
    SEARCH_MAX_PER_STORE = int(os.environ.get("SEARCH_MAX_PER_STORE", "24"))
    # 0 stops the automatic price checks (the "Check prices now" button still works).
    SCHEDULER = _flag("SCHEDULER", True)
    # Alert channels. The addresses to notify are set in Settings; the credentials stay here.
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "").strip()
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
