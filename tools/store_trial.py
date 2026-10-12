"""Can each store be searched and read from this machine?

Stores treat visitors differently depending on where they connect from, so this
is how to find out whether the tracker would work somewhere new (a cloud server,
a GitHub runner). For each store it opens a browser, sets the PIN code, runs one
search and reads the first listing found. Nothing is saved and no alert is sent.

    python tools/store_trial.py --pincode 560001 [--channel msedge] [--only croma,amazon]
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracker.browser import open_page  # noqa: E402
from tracker.stores import STORES  # noqa: E402

# One ordinary search per store; a brand's own store is asked about its own laptops.
QUERIES = {
    "lenovo": "Lenovo Legion laptop", "asus": "ASUS ROG laptop", "dell": "Dell Alienware laptop",
    "acer": "Acer Nitro laptop", "apple": "MacBook Air", "samsung": "Samsung Galaxy Book laptop",
}
DEFAULT_QUERY = "Lenovo Legion RTX 5070 laptop"


def where():
    """Roughly where this machine connects from, e.g. 'IN, Bengaluru (ACT Fibernet)'."""
    try:
        with urllib.request.urlopen("https://ipinfo.io/json", timeout=15) as response:
            found = json.load(response)
        return f"{found.get('country')}, {found.get('city')} ({found.get('org')})"
    except Exception as error:
        return f"unknown ({error})"


def try_store(store, pincode, channel):
    result = {"store": store.LABEL, "pin": "", "hits": "", "title": "", "price": "", "delivery": "", "problem": ""}
    began = time.monotonic()
    step = "open the store"
    try:
        with open_page(channel, True) as page:
            accepted = store.prepare(page, pincode)
            result["pin"] = "accepted" if accepted else "refused"
            step = "search"
            hits = store.search(page, QUERIES.get(store.KEY, DEFAULT_QUERY), 5)
            result["hits"] = len(hits)
            if hits:
                step = "read a listing"
                product = store.read(page, hits[0].url, pincode if accepted else None)
                result["title"] = product.title[:45]
                result["price"] = product.price_inr or "none shown"
                result["delivery"] = {True: "yes", False: "no", None: "not stated"}[product.deliverable]
            else:
                result["problem"] = "the search returned nothing"
    except Exception as error:
        message = str(error).splitlines()[0] if str(error) else type(error).__name__
        result["problem"] = f"could not {step}: {message[:110]}"
    result["seconds"] = round(time.monotonic() - began)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pincode", default="560001")
    parser.add_argument("--channel", default="", help="msedge or chrome; blank uses Playwright's own Chromium")
    parser.add_argument("--only", default="", help="comma-separated store keys; blank tries every store")
    args = parser.parse_args()
    keys = [key for key in args.only.split(",") if key] or list(STORES)

    place = where()
    print(f"Connecting from: {place}", flush=True)
    results = []
    for key in keys:
        results.append(try_store(STORES[key], args.pincode, args.channel))
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)

    worked = sum(1 for r in results if r["title"] and r["price"] != "none shown")
    lines = [f"## Store trial: {worked} of {len(results)} stores searched and read with a price", "",
             f"Connecting from: {place}. PIN code {args.pincode}.", "",
             "| Store | PIN code | Search hits | First listing | Price | Delivers | Problem | Seconds |",
             "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {r['store']} | {r['pin']} | {r['hits']} | {r['title']} | {r['price']} | {r['delivery']} | {r['problem']} | {r['seconds']} |"
              for r in results]
    report = "\n".join(lines)
    print("\n" + report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(report + "\n")


if __name__ == "__main__":
    main()
