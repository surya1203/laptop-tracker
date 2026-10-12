"""The stores the tracker can search. Each module follows the interface in base.py."""
from ..catalog import TOWER_RETAILERS
from . import acer, amazon, apple, asus, croma, dell, flipkart, lenovo, reliancedigital, samsung, vijaysales

STORES = {store.KEY: store for store in (
    amazon, flipkart, croma, vijaysales, reliancedigital,
    lenovo, asus, dell, acer, apple, samsung,
)}


def sells(store, brands, kind="laptop"):
    """Whether a store is worth searching for a hunt: a brand's own store only lists that brand,
    and only some stores sell tower PCs."""
    if kind == "tower" and store.KEY not in TOWER_RETAILERS:
        return False
    own = getattr(store, "BRANDS", None)
    return not own or not brands or any(brand.lower() in (name.lower() for name in own) for brand in brands)
