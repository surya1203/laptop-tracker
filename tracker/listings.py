"""Listings: product pages found for a hunt. Storage and the grouping the results page shows."""
import json

from . import matching
from .db import get_db, now

STATES = ("new", "tracked", "ignored")


def save(conn, hunt_id, retailer, product, specs, pincode):
    """Insert or refresh one listing and record this check's price. Returns True if it is new."""
    stamp = now()
    known = conn.execute("SELECT id FROM listings WHERE hunt_id = ? AND url = ?", (hunt_id, product.url)).fetchone()
    deliverable = None if product.deliverable is None else int(product.deliverable)
    values = (
        product.title, product.image_url, specs.get("model_number"),
        json.dumps(specs, ensure_ascii=False), json.dumps(product.raw_specs, ensure_ascii=False),
        stamp, deliverable, product.delivery_note, pincode if deliverable is not None else None,
    )
    if known:
        listing_id = known["id"]
        conn.execute(
            "UPDATE listings SET title = ?, image_url = ?, model_number = ?, specs = ?, raw_specs = ?, "
            "last_seen_at = ?, deliverable = ?, delivery_note = ?, delivery_pincode = ? WHERE id = ?",
            values + (listing_id,),
        )
    else:
        listing_id = conn.execute(
            "INSERT INTO listings (title, image_url, model_number, specs, raw_specs, last_seen_at, deliverable, "
            "delivery_note, delivery_pincode, hunt_id, retailer, url, first_seen_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values + (hunt_id, retailer, product.url, stamp),
        ).lastrowid
    conn.execute(
        "INSERT INTO price_points (listing_id, price_inr, mrp_inr, in_stock, checked_at) VALUES (?, ?, ?, ?, ?)",
        (listing_id, product.price_inr, product.mrp_inr, int(product.in_stock), stamp),
    )
    conn.commit()
    return not known


def ignored_urls(conn, hunt_id, retailer):
    rows = conn.execute(
        "SELECT url FROM listings WHERE hunt_id = ? AND retailer = ? AND state = 'ignored'", (hunt_id, retailer)
    )
    return {row["url"] for row in rows}


def for_hunt(hunt):
    """Every listing of a hunt with its latest price, sorted cheapest first and grouped for the tabs."""
    rows = get_db().execute(
        """
        SELECT l.*, p.price_inr, p.mrp_inr, p.in_stock, p.checked_at
        FROM listings l
        LEFT JOIN price_points p ON p.id = (
            SELECT id FROM price_points WHERE listing_id = l.id ORDER BY checked_at DESC, id DESC LIMIT 1
        )
        WHERE l.hunt_id = ?
        """,
        (hunt["id"],),
    ).fetchall()
    groups = {"match": [], "near": [], "miss": [], "tracked": [], "ignored": []}
    for row in rows:
        listing = dict(row)
        listing["specs"] = json.loads(listing["specs"] or "{}")
        listing["verdict"], listing["chips"] = matching.evaluate(hunt, listing)
        if listing["price_inr"] and listing["mrp_inr"] and listing["mrp_inr"] > listing["price_inr"]:
            listing["discount"] = round(100 * (1 - listing["price_inr"] / listing["mrp_inr"]))
        key = listing["state"] if listing["state"] != "new" else listing["verdict"]
        groups[key].append(listing)
    for items in groups.values():
        items.sort(key=lambda item: (item["price_inr"] is None, item["price_inr"] or 0, item["id"]))
    return groups


def review(hunt_id, shown, ticked):
    """Track the ticked listings; hide the other ones that were on screen. Returns (tracked, hidden)."""
    db = get_db()
    tracked = hidden = 0
    for listing_id in shown:
        state = "tracked" if listing_id in ticked else "ignored"
        changed = db.execute(
            "UPDATE listings SET state = ? WHERE id = ? AND hunt_id = ? AND state = 'new'",
            (state, listing_id, hunt_id),
        ).rowcount
        tracked += changed if state == "tracked" else 0
        hidden += changed if state == "ignored" else 0
    db.commit()
    return tracked, hidden


def set_state(hunt_id, listing_id, state):
    db = get_db()
    changed = db.execute(
        "UPDATE listings SET state = ? WHERE id = ? AND hunt_id = ?", (state, listing_id, hunt_id)
    ).rowcount
    db.commit()
    return bool(changed)


def restore_hidden(hunt_id):
    db = get_db()
    restored = db.execute(
        "UPDATE listings SET state = 'new' WHERE hunt_id = ? AND state = 'ignored'", (hunt_id,)
    ).rowcount
    db.commit()
    return restored
