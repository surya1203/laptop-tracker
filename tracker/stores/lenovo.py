"""Lenovo India's own store (lenovo.com/in): everything comes from its product search API."""
import re
from urllib.parse import quote, urlsplit

from .base import Hit, Product, StoreError, clean, fetch_json, rupees, without_brand

KEY = "lenovo"
LABEL = "Lenovo Store"
BRANDS = ("Lenovo",)
HOME = "https://www.lenovo.com/in/en"
SEARCH_API = "https://openapi.lenovo.com/in/en/ofp/search/global/cache/products/get/_tsc"
# Lenovo marks "build your own" models with this type; their price is for the starting configuration.
CUSTOMISABLE = "4"


def prepare(page, pincode):
    page.goto(f"{HOME}/laptops/", wait_until="domcontentloaded", timeout=45000)
    return True


def _products(page, text, rows):
    data = fetch_json(page, f"{SEARCH_API}?text={quote(text)}&rows={rows}&sort=Recommended", LABEL)
    try:
        groups = data["data"]["data"]
    except (KeyError, TypeError):
        return []
    return [item for group in groups or [] for item in group.get("products") or []]


def _title(item):
    name = re.sub(r"<[^>]+>", "", item.get("summary") or item.get("productName") or "")
    title = name if name.lower().startswith("lenovo") else f"Lenovo {name}"
    return clean(f"{title} (customisable, {item['productCode']})" if item.get("productType") == CUSTOMISABLE
                 else f"{title} ({item['productCode']})")


def search(page, query, limit):
    # The store only sells Lenovo, and searching for the brand name itself brings up accessories.
    text = re.sub(r"\blenovo\b|\blaptops?\b", " ", query, flags=re.I).strip() or "laptop"
    hits = []
    for item in _products(page, text, 40):
        if item.get("flCode") != "laptops" or not item.get("url") or not item.get("productCode"):
            continue
        hits.append(Hit(url=HOME + item["url"], title=_title(item)))
        if len(hits) >= limit:
            break
    return hits


def read(page, url, pincode):
    code = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1].upper()
    item = next((p for p in _products(page, code, 10) if str(p.get("productCode", "")).upper() == code), None)
    if not item:
        raise StoreError("Lenovo no longer lists this model.")
    specs = {"Brand": "Lenovo", "Part Number": item["productCode"]}
    for row in item.get("classification") or []:
        name, value = clean(row.get("a")), clean(re.sub(r"<[^>]+>", " ", str(row.get("b") or "")))
        if name and value and name not in specs:
            specs[name] = value.replace("®", "").replace("™", "")
    price, mrp = rupees(item.get("finalPrice")), rupees(item.get("webPrice"))
    image = ((item.get("media") or {}).get("heroImage") or {}).get("imageAddress")
    return Product(
        url=url, title=_title(item), image_url=(f"https:{image}" if image and image.startswith("//") else image) or None,
        price_inr=price, mrp_inr=mrp if mrp and price and mrp >= price else None,
        in_stock=bool(price) and item.get("marketingStatus") == "Available" and bool(item.get("purchaseFlag", True)),
        raw_specs=specs,
    )
