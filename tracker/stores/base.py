"""What every store module provides, and the values they hand back.

A store module has:
    KEY, LABEL
    prepare(page, pincode)        open the store and set the delivery PIN code, once per session
    search(page, query, limit)    -> [Hit, ...]
    read(page, url, pincode)      -> Product
and optionally:
    BRANDS                        a brand's own store lists only these brands, so other hunts skip it
"""
import json
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


def relevant(title, query):
    """Whether a result is worth opening: stores pad thin searches with unrelated products."""
    words = [word for word in re.findall(r"[a-z0-9]+", query.lower()) if word not in ("laptop", "laptops")]
    text = re.sub(r"[^a-z0-9]", "", title.lower())
    return sum(word in text for word in words) * 2 >= len(words)


def without_brand(query, brand):
    """A brand's own store sells nothing else, and searching it for the brand name brings up accessories."""
    return re.sub(rf"\b{re.escape(brand)}\b|\blaptops?\b", " ", query, flags=re.I).strip() or "laptop"


_FETCH_JS = """async ([url, options]) => {
    const response = await fetch(url, options);
    const text = await response.text();
    let data = null;
    try { data = JSON.parse(text); } catch (error) {}
    return {status: response.status, data};
}"""


def fetch_json(page, url, store, method="GET", headers=None, body=None):
    """Call one of a store's own data APIs from inside its page, so the request looks like the site's."""
    options = {"method": method, "headers": headers or {}}
    if body is not None:
        options["body"] = json.dumps(body)
        options["headers"] = {"Content-Type": "application/json", **options["headers"]}
    try:
        result = page.evaluate(_FETCH_JS, [url, options])
    except Exception as error:
        raise StoreError(f"{store}'s data could not be fetched.") from error
    if result["status"] != 200 or result["data"] is None:
        raise StoreError(f"{store} refused a data request (HTTP {result['status']}).")
    return result["data"]


_LD_JS = """() => [...document.querySelectorAll('script[type="application/ld+json"]')].map((s) => s.textContent)"""


def ld_product(page):
    """The schema.org Product block most shops embed in a product page, or {}."""
    for text in page.evaluate(_LD_JS):
        try:
            data = json.loads(text)
        except ValueError:
            continue
        for node in data if isinstance(data, list) else [data]:
            if isinstance(node, dict) and node.get("@type") == "Product":
                return node
    return {}


def ld_offer(node):
    """(price, in stock) from a schema.org Product block."""
    offers = node.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = rupees(offers.get("price") or offers.get("lowPrice"))
    return price, "instock" in str(offers.get("availability", "InStock")).lower().replace(" ", "")
