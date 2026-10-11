"""The stores the tracker can search. Each module follows the interface in base.py."""
from . import acer, amazon, apple, asus, croma, dell, flipkart, lenovo, reliancedigital, samsung, vijaysales

STORES = {store.KEY: store for store in (
    amazon, flipkart, croma, vijaysales, reliancedigital,
    lenovo, asus, dell, acer, apple, samsung,
)}


def sells(store, brands):
    """Whether a store is worth searching for a hunt's brands: a brand's own store only lists that brand."""
    own = getattr(store, "BRANDS", None)
    return not own or not brands or any(brand.lower() in (name.lower() for name in own) for brand in brands)
