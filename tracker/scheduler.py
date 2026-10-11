"""Runs the price check on a schedule while the app is open.

A background thread wakes up every half minute and starts a check once the
interval chosen in Settings has passed since the last one. The time of the last
check is kept in the database, so a restart does not reset the clock.
"""
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from . import checker
from .db import connect

INTERVALS = (1, 3, 6, 12, 24)  # hours
DEFAULT_INTERVAL = 6
WAKE_EVERY_SECONDS = 30
_started = False


def interval_hours(conn):
    row = conn.execute("SELECT value FROM settings WHERE key = 'check_interval_hours'").fetchone()
    try:
        hours = int(row["value"])
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL
    return hours if hours in INTERVALS else DEFAULT_INTERVAL


def next_check(conn):
    """When the next check is due (UTC). Now, if there has never been one."""
    row = conn.execute("SELECT value FROM settings WHERE key = 'last_check_at'").fetchone()
    if not row or not row["value"]:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(row["value"]) + timedelta(hours=interval_hours(conn))


def check_options(config):
    return {
        "database": config["DATABASE_PATH"], "channel": config["BROWSER_CHANNEL"], "headless": config["BROWSER_HEADLESS"],
        "mail": {"sender": config["SENDER_EMAIL"], "password": config["GMAIL_APP_PASSWORD"],
                 "callmebot_key": config["CALLMEBOT_API_KEY"]},
    }


def _loop(app):
    options = check_options(app.config)
    while True:
        time.sleep(WAKE_EVERY_SECONDS)
        try:
            conn = connect(options["database"])
            try:
                due = next_check(conn) <= datetime.now(timezone.utc) and bool(checker.due_listings(conn))
            finally:
                conn.close()
            if due and not checker.RUN["running"]:
                checker.run(options)
        except Exception as error:  # the schedule must survive one bad round
            app.logger.warning("Scheduled price check failed: %s", error)


def start(app):
    """Start the schedule once per process. Flask's reloader runs the app twice; only its worker gets one."""
    global _started
    if _started or not app.config["SCHEDULER"]:
        return
    if app.config["DEBUG"] and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    _started = True
    threading.Thread(target=_loop, args=(app,), daemon=True, name="price-check-schedule").start()
