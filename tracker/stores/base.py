"""What every store module provides, and the values they hand back.

A store module has:
    KEY, LABEL
    prepare(page, pincode)        open the store and set the delivery PIN code, once per session
    search(page, query, limit)    -> [Hit, ...]
    read(page, url, pincode)      -> Product
"""
import re
from dataclasses import dataclass, field


class StoreError(Exception):
    """The store could not be read: blocked, changed its layout, or timed out."""


@dataclass
class Hit:
    url: str
    title: str = ""


@dataclass
class Product:
    url: str
    title: str
    image_url: str | None = None
    price_inr: int | None = None
    mrp_inr: int | None = None
    in_stock: bool = True
    raw_specs: dict = field(default_factory=dict)
    # None = no PIN code set, or the store did not say.
    deliverable: bool | None = None
    delivery_note: str | None = None


def rupees(text):
    """'₹1,69,990.00' -> 169990. None when there is no amount."""
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(text or ""))
    if not match:
        return None
    value = float(match.group().replace(",", ""))
    return int(round(value)) if value > 0 else None


def clean(text):
    return " ".join(str(text or "").replace("‎", "").replace("‏", "").split())
