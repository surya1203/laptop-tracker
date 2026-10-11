"""Dell India's own store (dellstore.com, where dell.com/en-in sends shoppers)."""
from . import magento
from .base import without_brand

KEY = "dell"
LABEL = "Dell Store"
BRANDS = ("Dell",)
HOME = "https://www.dellstore.com"


def prepare(page, pincode):
    page.goto(HOME, wait_until="domcontentloaded", timeout=45000)
    return True


def search(page, query, limit):
    return magento.search(page, HOME, without_brand(query, "Dell"), limit, LABEL)


def read(page, url, pincode):
    product = magento.read(page, url, LABEL, "Dell")
    # Dell gives every configuration of a model the same name; the code at the end of its address tells them apart.
    code = url.rsplit("/", 1)[-1].removesuffix(".html").rsplit("-", 1)[-1].upper()
    product.raw_specs.setdefault("Model Number", code)
    product.title = f"{product.title} ({code})"
    return product
