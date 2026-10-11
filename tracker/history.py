"""Price history of one listing: lows, change since the last check, and a sparkline.

Everything is worked out from the tracker's own price points. A check where the
listing was out of stock, or showed no price, is kept but never counts as a low.
"""
from datetime import datetime, timedelta, timezone

SPARK_WIDTH, SPARK_HEIGHT = 120, 28


def _when(point):
    return datetime.fromisoformat(point["checked_at"])


def summary(points, now=None):
    """`points` are a listing's price checks, oldest first."""
    now = now or datetime.now(timezone.utc)
    priced = [p for p in points if p["price_inr"] and p["in_stock"]]
    latest = points[-1] if points else None
    current = latest["price_inr"] if latest else None
    earlier = [p for p in priced if p is not latest]
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
        "checks": len(points),
        "previous_inr": previous,
        "change_inr": current - previous if buyable and previous else None,
        "low_inr": low["price_inr"] if low else None,
        "low_at": low["checked_at"] if low else None,
        "low_30_inr": low_30["price_inr"] if low_30 else None,
        "low_30_at": low_30["checked_at"] if low_30 else None,
        # Only worth saying once it has been dearer than this.
        "at_low": bool(buyable and low and current <= low["price_inr"] and max(p["price_inr"] for p in priced) > current),
        "above_low_inr": current - low["price_inr"] if buyable and low else None,
        "spark": sparkline(priced),
    }


def sparkline(priced):
    """Points for an SVG polyline of the price over time, or None with fewer than two checks."""
    if len(priced) < 2:
        return None
    start, end = _when(priced[0]), _when(priced[-1])
    span = (end - start).total_seconds() or 1
    prices = [p["price_inr"] for p in priced]
    bottom, top = min(prices), max(prices)
    height = (top - bottom) or 1
    coordinates = []
    for point in priced:
        x = 2 + (SPARK_WIDTH - 4) * (_when(point) - start).total_seconds() / span
        y = 3 + (SPARK_HEIGHT - 6) * (1 - (point["price_inr"] - bottom) / height) if top != bottom else SPARK_HEIGHT / 2
        coordinates.append(f"{x:.1f},{y:.1f}")
    return " ".join(coordinates)
