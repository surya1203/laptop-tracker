"""SQLite connection handling and first-run setup."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, g

DEFAULT_SETTINGS = {
    "check_interval_hours": "6",
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def get_setting(key, default=None):
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def init_db(app):
    """Create tables, seed default settings and import the old saved searches once."""
    from . import migrate

    conn = connect(app.config["DATABASE_PATH"])
    try:
        conn.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
        conn.executemany(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", DEFAULT_SETTINGS.items()
        )
        conn.commit()
        done = conn.execute("SELECT 1 FROM settings WHERE key = 'legacy_imported'").fetchone()
        if not done:
            for line in migrate.import_legacy(conn, app.config["LEGACY_DATABASE_PATH"]):
                app.logger.warning(line)
            conn.execute("INSERT INTO settings (key, value) VALUES ('legacy_imported', ?)", (now(),))
            conn.commit()
    finally:
        conn.close()
