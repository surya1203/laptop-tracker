"""Alerts: decides when a price check is worth telling you about, and sends it.

Rules are set per hunt. Every alert is written to the in-app feed; email (Gmail)
and WhatsApp (CallMeBot) are sent as well when they are set up in Settings, outside quiet hours.
A rule does not fire twice for the same listing within the cooldown.
"""
import json
import smtplib
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from . import catalog
from .db import now

RULES = {
    "new_low": "New all-time low",
    "target": "Target price reached",
    "drop": "Price drop",
    "back_in_stock": "Back in stock",
    "test": "Test alert",
}
DEFAULT_COOLDOWN_HOURS = 24


def rupees(amount):
    """189990 -> '₹1,89,990'."""
    digits = str(int(amount))
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return "₹" + ",".join(([head] if head else []) + groups + [tail])


def triggered(hunt, points):
    """The rules a listing's newest price check sets off: [(rule, detail), ...]. `points` are oldest first."""
    if len(points) < 2:
        return []
    latest, before = points[-1], points[:-1]
    price = latest["price_inr"]
    if not price or not latest["in_stock"]:
        return []
    priced = [p["price_inr"] for p in before if p["price_inr"] and p["in_stock"]]
    previous = priced[-1] if priced else None
    found = []
    if hunt["alert_new_low"] and priced and price < min(priced):
        found.append(("new_low", f"{rupees(price)}, down from the earlier low of {rupees(min(priced))}"))
    target = hunt["alert_target_inr"]
    if target and price <= target and (previous is None or previous > target):
        found.append(("target", f"{rupees(price)}, at or under your target of {rupees(target)}"))
    drop = hunt["alert_drop_pct"]
    if drop and previous and price <= previous * (1 - drop / 100):
        found.append(("drop", f"{rupees(price)}, {round(100 * (1 - price / previous))}% below the last check ({rupees(previous)})"))
    if hunt["alert_back_in_stock"] and not before[-1]["in_stock"]:
        found.append(("back_in_stock", f"buyable again at {rupees(price)}"))
    return found


def _setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row and row["value"] else default


def in_quiet_hours(start, end, moment=None):
    """Whether the local time falls in the quiet window, e.g. '22:00' to '07:00' (which wraps past midnight)."""
    if not start or not end or start == end:
        return False
    clock = (moment or datetime.now()).strftime("%H:%M")
    return start <= clock < end if start < end else clock >= start or clock < end


def credentials(conn, fallback=None):
    """What the channels sign in with: the values saved in Settings, else the ones in .env (`fallback`)."""
    fallback = fallback or {}
    return {
        "sender": _setting(conn, "sender_email") or fallback.get("sender") or "",
        "password": (_setting(conn, "gmail_app_password") or fallback.get("password") or "").replace(" ", ""),
        "callmebot_key": _setting(conn, "callmebot_api_key") or fallback.get("callmebot_key") or "",
    }


def send_email(mail, to, subject, body):
    if not (mail.get("sender") and mail.get("password")):
        raise RuntimeError("Enter the Gmail address to send from and its app password in Settings first.")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = mail["sender"], to, subject
    message.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(mail["sender"], mail["password"])
            server.send_message(message)
    except smtplib.SMTPAuthenticationError as error:
        raise RuntimeError("Gmail refused the sign-in. It needs a 16-letter app password, not your normal password.") from error
    except (smtplib.SMTPServerDisconnected, OSError):
        # Some networks block the secure port; Gmail also accepts mail on 587.
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(mail["sender"], mail["password"])
            server.send_message(message)


def send_whatsapp(mail, phone, body):
    if not mail.get("callmebot_key"):
        raise RuntimeError("Enter your CallMeBot key in Settings first.")
    query = urllib.parse.urlencode({"phone": phone, "text": body, "apikey": mail["callmebot_key"]})
    with urllib.request.urlopen(f"https://api.callmebot.com/whatsapp.php?{query}", timeout=30) as response:
        answer = response.read().decode("utf-8", "replace")
    if response.status != 200 or "error" in answer.lower():
        raise RuntimeError(f"CallMeBot answered: {answer[:120]}")


def deliver(conn, mail, subject, body, quiet_ok=False):
    """Send to every channel that is set up. Returns (channels reached, problems)."""
    reached, problems = ["feed"], []
    mail = credentials(conn, mail)
    if not quiet_ok and in_quiet_hours(_setting(conn, "quiet_start"), _setting(conn, "quiet_end")):
        return reached, ["quiet hours: shown here only"]
    for channel, address, send in (
        ("email", _setting(conn, "notify_email") or (mail["sender"] if mail["password"] else None),
         lambda to: send_email(mail, to, subject, body)),
        ("whatsapp", _setting(conn, "notify_whatsapp"), lambda to: send_whatsapp(mail, to, body)),
    ):
        if not address:
            continue
        try:
            send(address)
            reached.append(channel)
        except Exception as error:
            problems.append(f"{channel} failed: {str(error).splitlines()[0][:160]}")
    return reached, problems


def after_check(conn, mail, hunt, listing, points):
    """Raise whatever alerts the newest check of a tracked listing calls for. Returns how many were raised."""
    cooldown = float(_setting(conn, "alert_cooldown_hours", DEFAULT_COOLDOWN_HOURS))
    since = (datetime.now(timezone.utc) - timedelta(hours=cooldown)).isoformat(timespec="seconds")
    raised = 0
    for rule, detail in triggered(hunt, points):
        repeat = conn.execute(
            "SELECT 1 FROM alerts WHERE listing_id = ? AND rule = ? AND sent_at >= ?", (listing["id"], rule, since)
        ).fetchone()
        if repeat:
            continue
        store = catalog.RETAILER_LABELS.get(listing["retailer"], listing["retailer"])
        subject = f"{RULES[rule]}: {listing['title'][:70]}"
        body = f"{RULES[rule]}: {detail}\n{listing['title']}\n{store} · hunt “{hunt['name']}”\n{listing['url']}"
        reached, problems = deliver(conn, mail, subject, body)
        conn.execute(
            "INSERT INTO alerts (hunt_id, listing_id, rule, channel, price_inr, message, sent_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (hunt["id"], listing["id"], rule, ", ".join(reached), points[-1]["price_inr"],
             json.dumps({"detail": detail, "problems": problems}, ensure_ascii=False), now()),
        )
        conn.commit()
        raised += 1
    return raised


def recent(conn, limit=30):
    """The alert feed, newest first."""
    rows = conn.execute(
        """
        SELECT a.*, l.title, l.url, l.retailer, h.name AS hunt_name
        FROM alerts a
        LEFT JOIN listings l ON l.id = a.listing_id
        LEFT JOIN hunts h ON h.id = a.hunt_id
        ORDER BY a.sent_at DESC, a.id DESC LIMIT ?
        """, (limit,),
    ).fetchall()
    feed = []
    for row in rows:
        alert = dict(row)
        try:
            extra = json.loads(alert["message"] or "{}")
        except ValueError:
            extra = {"detail": alert["message"]}
        alert.update(label=RULES.get(alert["rule"], alert["rule"]), detail=extra.get("detail"), problems=extra.get("problems") or [])
        feed.append(alert)
    return feed
