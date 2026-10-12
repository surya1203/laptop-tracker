"""Earlier prices for a tracked listing, from before the tracker first saw it.

BuyHatke (buyhatke.com) has recorded prices at most Indian stores for years. It
has no published API: this reads what its own pages load, so it can stop working
without notice, and it turns callers away after a few dozen quick requests. So
each tracked listing is looked up once, slowly, and the result is remembered.

Imported prices are stored as price points marked with their source. They count
towards the lows and the chart; importing them never raises an alert.
"""
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from .db import connect, now

SOURCE = "buyhatke"
HOME = "https://buyhatke.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36"}
# BuyHatke's times carry no zone; they are Indian time.
IST = timezone(timedelta(hours=5, minutes=30))
# Some store links cover several configurations. If BuyHatke's price for the link is further than this
# from the store's own, it is probably a different configuration and its history would mislead.
MAX_PRICE_GAP = 0.15
PAUSE_SECONDS = 15        # between two listings in one round
PER_ROUND = 2             # listings looked up each time the schedule wakes
RETRY_AFTER_SECONDS = 1800  # after BuyHatke refuses or cannot be reached

_STEP = re.compile(r'\{from:"([^"]+)",to:"([^"]+)",price:(\d+(?:\.\d+)?)\}')
_stores = None
_wait_until = 0.0


class Unavailable(Exception):
    """BuyHatke has nothing usable for this listing; the message says why. Not worth asking again."""


class Busy(Exception):
    """BuyHatke refused or could not be reached. Worth asking again later."""


def _get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=40) as response:
            return response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as error:
        raise Busy(f"BuyHatke could not be read: {error}") from error


def locate(url, stores):
    """(BuyHatke's store number, the product id it files this link under), or None if it does not cover the store.

    `stores` is BuyHatke's own table of stores, with the patterns that pull a product id out of a link.
    """
    host = urlsplit(url).netloc.lower()
    best = None
    for prefix, endings in stores.items():
        for ending in endings:
            for suffix, entries in ending.items():
                domain = prefix + suffix
                if host in (domain, domain.removeprefix("www.")) or host.endswith("." + domain):
                    if entries and (best is None or len(domain) > best[0]):
                        best = (len(domain), entries[0]["pos"], (entries[0].get("config") or {}).get("pidRegex") or [])
    if not best:
        return None
    for pattern in best[2]:
        try:
            match = re.search(pattern, url)
        except re.error:
            continue
        if match:
            return best[1], match.group(1) if match.groups() else match.group(0)
    return None


def points_from(page, before):
    """Price points from a BuyHatke product page, oldest first, keeping only those earlier than `before` (UTC).

    The page lists stretches of time a price held for. Each becomes a point at its start and one at its end,
    so a long steady stretch still draws as a flat line.
    """
    found = {}
    for start, end, price in _STEP.findall(page):
        for stamp in (start, end):
            try:
                moment = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST).astimezone(timezone.utc)
            except ValueError:
                continue
            if moment < before and float(price) > 0:
                found[moment] = round(float(price))
    return sorted(found.items())


def fetch(url, before):
    """What BuyHatke knows about a store link: {"points": [(utc time, price), ...], "current": its latest price}."""
    global _stores
    if _stores is None:
        _stores = json.loads(_get(f"{HOME}/api/getGlobalPosAndPid"))["data"]
    place = locate(url, _stores)
    if not place:
        raise Unavailable("BuyHatke does not follow this store.")
    pos, pid = place
    record = json.loads(_get(f"{HOME}/api/productData?pos={pos}&pid={urllib.request.quote(str(pid), safe='')}"))
    data = record.get("data") or {}
    if not record.get("status") or not data.get("internalPid"):
        raise Unavailable("BuyHatke has not recorded this listing.")
    page = _get(f"{HOME}/x-price-in-india-{pos}-{data['internalPid']}")
    return {"points": points_from(page, before), "current": data.get("cur_price")}


def import_listing(conn, listing, fetcher=fetch):
    """Look one tracked listing up and store its earlier prices. Returns the note saved with the listing."""
    own = conn.execute(
        "SELECT MIN(checked_at) AS first FROM price_points WHERE listing_id = ? AND source IS NULL", (listing["id"],)
    ).fetchone()["first"]
    latest = conn.execute(
        "SELECT price_inr FROM price_points WHERE listing_id = ? AND source IS NULL AND price_inr IS NOT NULL "
        "ORDER BY checked_at DESC, id DESC LIMIT 1", (listing["id"],)
    ).fetchone()
    before = datetime.fromisoformat(own) if own else datetime.now(timezone.utc)
    try:
        found = fetcher(listing["url"], before)
    except Unavailable as error:
        note, points = str(error), []
    else:
        points, theirs, ours = found["points"], found["current"], latest["price_inr"] if latest else None
        if not points:
            note = "BuyHatke has no prices from before this listing was tracked."
        elif theirs and ours and abs(theirs - ours) / ours > MAX_PRICE_GAP:
            note, points = "BuyHatke's price for this link is far from the store's, so it may be another configuration. Nothing was imported.", []
        else:
            first = points[0][0].astimezone()
            note = f"Prices before tracking began are from BuyHatke, back to {first.day} {first:%b %Y}."
    conn.execute("DELETE FROM price_points WHERE listing_id = ? AND source = ?", (listing["id"], SOURCE))
    conn.executemany(
        "INSERT INTO price_points (listing_id, price_inr, in_stock, checked_at, source) VALUES (?, ?, 1, ?, ?)",
        [(listing["id"], price, moment.isoformat(timespec="seconds"), SOURCE) for moment, price in points],
    )
    conn.execute("UPDATE listings SET history_checked_at = ?, history_note = ? WHERE id = ?", (now(), note, listing["id"]))
    conn.commit()
    return note


def pending(conn, limit=PER_ROUND):
    """Tracked listings that have not been looked up yet."""
    return conn.execute(
        """
        SELECT l.id, l.url FROM listings l JOIN hunts h ON h.id = l.hunt_id
        WHERE l.state = 'tracked' AND l.history_checked_at IS NULL AND h.deleted_at IS NULL
        ORDER BY l.id LIMIT ?
        """, (limit,),
    ).fetchall()


def run_pending(database):
    """Look up a few waiting listings. Returns how many were done; quietly does nothing while BuyHatke is resting."""
    global _wait_until
    if time.monotonic() < _wait_until:
        return 0
    conn = connect(database)
    try:
        done = 0
        for listing in pending(conn):
            if done:
                time.sleep(PAUSE_SECONDS)
            try:
                import_listing(conn, listing)
            except Busy:
                _wait_until = time.monotonic() + RETRY_AFTER_SECONDS
                raise
            done += 1
        return done
    finally:
        conn.close()
