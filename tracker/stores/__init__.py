"""One module per store, all behind the interface described in base.py."""
from . import amazon, flipkart

STORES = {store.KEY: store for store in (amazon, flipkart)}
