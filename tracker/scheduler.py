"""Runs the price check, and the search for new listings, on a schedule while the app is open.

A background thread wakes up every half minute and starts a check once the
interval chosen in Settings has passed since the last one. If asked to, it then
sends an update on every tracked listing, changed or not. The time of the last
check is kept in the database, so a restart does not reset the clock. Active
hunts are searched again on a slower schedule of their own, one hunt at a time.
"""
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from . import alerts, backfill, checker, hunts, listings, search
from .db import connect, get_db, get_setting, now, set_setting

INTERVALS = (1, 3, 6, 12, 24)  # hours
DEFAULT_INTERVAL = 6
# How often active hunts are searched again for new listings: (hours, label). 0 = only when you press Search now.
SEARCH_CHOICES = ((0, "Off"), (12, "Every 12 hours"), (24, "Once a day"), (48, "Every 2 days"), (168, "Once a week"))
DEFAULT_SEARCH_INTERVAL = 24
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


def search_interval_hours(conn):
    row = conn.execute("SELECT value FROM settings WHERE key = 'search_interval_hours'").fetchone()
    try:
        hours = int(row["value"])
    except (TypeError, ValueError):
        return DEFAULT_SEARCH_INTERVAL
    return hours if hours in dict(SEARCH_CHOICES) else DEFAULT_SEARCH_INTERVAL


def last_search(conn):
    """When hunts were last searched on the schedule; before the first time, the latest search of any hunt."""
    row = conn.execute("SELECT value FROM settings WHERE key = 'last_search_at'").fetchone()
    if row and row["value"]:
        return row["value"]
    return conn.execute("SELECT MAX(last_searched_at) AS at FROM hunts WHERE deleted_at IS NULL").fetchone()["at"]


def next_search(conn):
    """When hunts are next searched for new listings (UTC). None if that is switched off."""
    hours = search_interval_hours(conn)
    if not hours:
        return None
    last = last_search(conn)
    return datetime.fromisoformat(last) + timedelta(hours=hours) if last else datetime.now(timezone.utc)


def search_hunts(app, options):
    """Search every active hunt again, one after another, and raise an alert for new listings that match."""
    with app.app_context():
        config = app.config
        for hunt in hunts.all_hunts():
            if hunt["status"] != "active":
                continue
            began = now()
            started = search.start(hunt, {
                "database": config["DATABASE_PATH"], "channel": config["BROWSER_CHANNEL"],
                "headless": config["BROWSER_HEADLESS"], "limit": config["SEARCH_MAX_PER_STORE"],
                "pincode": get_setting("delivery_pincode"),
            })
            if not started:
                continue
            while search.running(hunt["id"]):
                time.sleep(5)
            fresh = [found for found in listings.for_hunt(hunt)["match"] if found["first_seen_at"] >= began]
            if fresh and hunt["alert_new_match"]:
                alerts.new_matches(get_db(), options["mail"], hunt, fresh)
        set_setting("last_search_at", now())


def claim_round(conn, minutes=10):
    """Take this round of checks, unless another copy of the app sharing the database took it moments ago.

    Two copies left running would otherwise each check every listing and each send an update.
    """
    stamp = datetime.now(timezone.utc)
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('check_claimed_at', '')")
    taken = conn.execute("UPDATE settings SET value = ? WHERE key = 'check_claimed_at' AND value < ?",
                         (stamp.isoformat(timespec="seconds"), (stamp - timedelta(minutes=minutes)).isoformat(timespec="seconds")))
    conn.commit()
    return taken.rowcount == 1


def send_update(app, options, since):
    """After a scheduled round that began at `since`, send where every tracked listing stands, if that is switched on."""
    with app.app_context():
        if get_setting("status_updates") != "1":
            return
        items = [listing for group in listings.tracked() for listing in group["listings"] if listing["hunt_status"] == "active"]
        if items:
            _, _, problems = alerts.status_update(get_db(), options["mail"], items, since, get_setting("last_update_at"))
            set_setting("last_update_at", now())
            for problem in problems:
                app.logger.warning("Update after the check: %s", problem)


def check_options(config):
    return {
        "database": config["DATABASE_PATH"], "channel": config["BROWSER_CHANNEL"], "headless": config["BROWSER_HEADLESS"],
        "mail": {"sender": config["SENDER_EMAIL"], "password": config["GMAIL_APP_PASSWORD"],
                 "telegram_token": config["TELEGRAM_BOT_TOKEN"], "discord_webhook": config["DISCORD_WEBHOOK_URL"]},
    }


def _loop(app):
    options = check_options(app.config)
    while True:
        time.sleep(WAKE_EVERY_SECONDS)
        try:
            conn = connect(options["database"])
            try:
                due = next_check(conn) <= datetime.now(timezone.utc) and bool(checker.due_listings(conn))
                due = due and not checker.RUN["running"] and claim_round(conn)
                search_at = next_search(conn)
            finally:
                conn.close()
            began = now()
            checked = due and not checker.RUN["running"] and checker.run(options)
            # Searches come after the check, never alongside it: both drive several browsers.
            if search_at and search_at <= datetime.now(timezone.utc) and not checker.RUN["running"]:
                search_hunts(app, options)
            # The update waits for the search, so its title can name new listings as well as new lows.
            if checked:
                send_update(app, options, began)
        except Exception as error:  # the schedule must survive one bad round
            app.logger.warning("Scheduled price check or search failed: %s", error)
        try:
            backfill.run_pending(options["database"])
        except Exception as error:
            app.logger.warning("Earlier prices could not be imported: %s", error)


def start(app):
    """Start the schedule once per process. Flask's reloader runs the app twice; only its worker gets one."""
    global _started
    if _started or not app.config["SCHEDULER"]:
        return
    if app.config["DEBUG"] and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    _started = True
    threading.Thread(target=_loop, args=(app,), daemon=True, name="price-check-schedule").start()
