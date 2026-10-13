"""Price history of one listing: lows, change since the last check, and a 30-day sparkline.

Worked out from a listing's price points: the tracker's own checks, plus any
earlier prices imported for it (see backfill.py). A check where the listing was
out of stock, or showed no price, is kept but never counts as a low.
"""
from datetime import datetime, timedelta, timezone

SPARK_WIDTH, SPARK_HEIGHT = 120, 28
SPARK_DAYS = 30
# Points this close together belong to one round of checks (a second copy of the app, or "Check now" pressed
# straight after), so the newest is not compared with them.
SAME_ROUND = timedelta(minutes=10)


def _when(point):
    return datetime.fromisoformat(point["checked_at"])


def _imported(point):
    try:
        return bool(point["source"])
    except (KeyError, IndexError):
        return False


def summary(points, now=None):
    """`points` are a listing's price checks, oldest first."""
    now = now or datetime.now(timezone.utc)
    priced = [p for p in points if p["price_inr"] and p["in_stock"]]
    latest = points[-1] if points else None
    current = latest["price_inr"] if latest else None
    earlier = [p for p in priced if _when(p) <= _when(latest) - SAME_ROUND]
    previous = earlier[-1]["price_inr"] if earlier else None
    low = min(priced, key=lambda p: p["price_inr"], default=None)
    recent = [p for p in priced if _when(p) >= now - timedelta(days=30)]
    low_30 = min(recent, key=lambda p: p["price_inr"], default=None)
    buyable = bool(latest and latest["in_stock"] and current)
    return {
        "price_inr": current,
        "mrp_inr": latest["mrp_inr"] if latest else None,
        "in_stock": bool(latest["in_stock"]) if latest else False,
        "checked_at": latest["checked_at"] if latest else None,
        "checks": sum(1 for p in points if not _imported(p)),
        "since_at": priced[0]["checked_at"] if priced else None,
        "imported": any(_imported(p) for p in points),
        "previous_inr": previous,
        "change_inr": current - previous if buyable and previous else None,
        "low_inr": low["price_inr"] if low else None,
        "low_at": low["checked_at"] if low else None,
        "low_30_inr": low_30["price_inr"] if low_30 else None,
        "low_30_at": low_30["checked_at"] if low_30 else None,
        # Only worth saying once it has been dearer than this.
        "at_low": bool(buyable and low and current <= low["price_inr"] and max(p["price_inr"] for p in priced) > current),
        "above_low_inr": current - low["price_inr"] if buyable and low else None,
        "spark": sparkline(priced, now),
    }


def sparkline(priced, now):
    """Step lines for the small chart: the last 30 days, the tracker's checks and imported prices apart.

    Returns {"own": "x,y x,y ...", "imported": "..."} for SVG polylines on one shared scale (a series with
    nothing to draw is left out), or None with fewer than two prices to show. A price holds until the next
    one, so each line runs flat and then steps; the imported line runs up to where the tracker's begins.
    """
    start = now - timedelta(days=SPARK_DAYS)
    lines, known = {}, 0
    for key in ("own", "imported"):
        mine = [p for p in priced if _imported(p) == (key == "imported")]
        line = [(_when(p), p["price_inr"]) for p in mine if _when(p) >= start]
        earlier = [p for p in mine if _when(p) < start]
        if earlier:  # the price it entered the 30 days at
            line.insert(0, (start, earlier[-1]["price_inr"]))
        known += len(line)
        if line:
            until = now if key == "own" or "own" not in lines else lines["own"][0][0]
            if until > line[-1][0]:
                line.append((until, line[-1][1]))
            if line[-1][0] > line[0][0]:
                lines[key] = line
    if known < 2 or not lines:
        return None
    first = min(line[0][0] for line in lines.values())
    span = (now - first).total_seconds() or 1
    prices = [price for line in lines.values() for _, price in line]
    bottom, top = min(prices), max(prices)

    def place(moment, price):
        x = 2 + (SPARK_WIDTH - 4) * (moment - first).total_seconds() / span
        y = 3 + (SPARK_HEIGHT - 6) * (1 - (price - bottom) / (top - bottom)) if top != bottom else SPARK_HEIGHT / 2
        return f"{x:.1f},{y:.1f}"

    drawn = {}
    for key, line in lines.items():
        coordinates = [place(*line[0])]
        for (_, before), (moment, price) in zip(line, line[1:]):
            coordinates += [place(moment, before), place(moment, price)]
        drawn[key] = " ".join(dict.fromkeys(coordinates))
    return drawn
