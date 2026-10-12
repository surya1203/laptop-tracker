"""Dell India's own store (dellstore.com, where dell.com/en-in sends shoppers)."""
import re

from . import magento
from .base import is_tower, without_brand

KEY = "dell"
LABEL = "Dell Store"
BRANDS = ("Dell",)
HOME = "https://www.dellstore.com"


def prepare(page, pincode):
    page.goto(HOME, wait_until="domcontentloaded", timeout=45000)
    return True


def search(page, query, limit, kind="laptop"):
    hits = magento.search(page, HOME, without_brand(query, "Dell"), 36 if kind == "tower" else limit, LABEL)
    if kind == "tower":  # the store has no categories to search within, so go by what a listing calls itself
        hits = [hit for hit in hits if re.search(r"desktop|tower", hit.title, re.I) and is_tower(hit.title)
                and not re.search(r"\b(slim|micro)\b", hit.title, re.I)]
    return hits[:limit]


def read(page, url, pincode):
    product = magento.read(page, url, LABEL, "Dell")
    # Dell gives every configuration of a model the same name; the code at the end of its address tells them apart.
    code = url.rsplit("/", 1)[-1].removesuffix(".html").rsplit("-", 1)[-1].upper()
    product.raw_specs.setdefault("Model Number", code)
    product.title = f"{product.title} ({code})"
    return product
