"""ASUS India's own store (asus.com/in/store, which sells through in.store.asus.com).

The store has no working search and only a few dozen laptops, so a "search" reads
its laptop listing and puts the models closest to the phrase first.
"""
import re

from . import magento
from .base import Hit, clean, without_brand

KEY = "asus"
LABEL = "ASUS Store"
BRANDS = ("ASUS",)
HOME = "https://www.asus.com/in/store"
LISTING = f"{HOME}/laptops/"

_LISTING_JS = """() => [...document.querySelectorAll('a[href*="in.store.asus.com"][href*=".html"]')].map((a) => ({
    href: a.href,
    title: a.getAttribute('aria-label') || a.textContent || '',
}))"""


def prepare(page, pincode):
    page.goto(LISTING, wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_selector('a[href*="in.store.asus.com"][href*=".html"]', timeout=20000)
    except Exception:
        pass
    return True


def _name(url):
    """'.../gaming-laptop-rog-strix-g16-g614p.html?config=X' -> 'ASUS ROG Strix G16 G614P'."""
    slug = url.split("?")[0].rsplit("/", 1)[-1].removesuffix(".html")
    slug = re.sub(r"^(ai-powered-|light-weight-|gaming-|creator-|thin-and-light-)*laptop-", "", slug)
    words = [word.upper() if re.search(r"\d", word) or word in ("rog", "tuf", "asus") else word.title() for word in slug.split("-")]
    name = " ".join(words)
    return name if name.upper().startswith("ASUS") else f"ASUS {name}"


def search(page, query, limit):
    if not page.url.startswith(LISTING):
        prepare(page, None)
    words = re.findall(r"[a-z0-9]+", without_brand(query, "ASUS").lower())
    found = {}
    for item in page.evaluate(_LISTING_JS):
        url = item["href"].split("#")[0]
        if "/asus-for-education" in url or "/purchase/" in url:
            continue
        title = re.sub(r"^(Learn more|Buy)( about)?\s+", "", clean(item["title"]))
        found.setdefault(url, title if len(title) > 8 else _name(url))
    def closeness(entry):
        text = re.sub(r"[^a-z0-9]", "", f"{entry[0]} {entry[1]}".lower())
        return -sum(word in text for word in words)
    return [Hit(url=url, title=title) for url, title in sorted(found.items(), key=closeness)[:limit]]


def read(page, url, pincode):
    product = magento.read(page, url, LABEL, "ASUS", settle_ms=2500)
    config = re.search(r"[?&]config=([\w-]+)", url)
    if config:
        product.raw_specs.setdefault("Part Number", config.group(1))
        product.title = f"{product.title} ({config.group(1)})"
    return product
