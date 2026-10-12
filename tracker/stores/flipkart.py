"""Flipkart: search results from the page, product details from Flipkart's own page-data API.

The product page only renders its spec sheet after a couple of clicks, but the
API the page itself calls returns specs, price, stock and whether the item can be
delivered to a PIN code in one response. It is called from inside the page so it
carries the browser's cookies.
"""
import html
import re
from urllib.parse import parse_qs, quote_plus, urlsplit

from .base import Hit, Product, StoreError, clean, relevant, rupees

KEY = "flipkart"
LABEL = "Flipkart"
HOME = "https://www.flipkart.com"
# Flipkart's "Laptops" and "Tower PCs" categories, to keep accessories out of the results.
SIDS = {"laptop": "6bo,b5g", "tower": "6bo,nl4,dze"}

_SEARCH_JS = """() => [...document.querySelectorAll('a[href*="/p/itm"]')].map((a) => ({
    href: a.getAttribute('href'),
    title: (a.querySelector('img') && a.querySelector('img').alt) || a.getAttribute('title') || '',
    ad: /\\bAD\\b|Sponsored/.test(a.textContent.slice(0, 40)),
}))"""

# Flipkart pins each session to one of its data centres and answers 406, naming the right one, when
# asked on another. So: try a host, and follow the redirect it describes.
_FETCH_JS = """async ([body, agent]) => {
    let host = window.__trackerHost || '1';
    let status = 0;
    for (let attempt = 0; attempt < 3; attempt++) {
        const response = await fetch(`https://${host}.rome.api.flipkart.com/api/4/page/fetch`, {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json', 'X-User-Agent': agent + ' FKUA/website/42/website/Desktop'},
            body: JSON.stringify(body),
        });
        status = response.status;
        if (response.ok) { window.__trackerHost = host; return {status, data: await response.json()}; }
        let wanted = null;
        try { wanted = String((await response.json()).RESPONSE.id || ''); } catch (error) {}
        if (status !== 406 || !/^\\d+$/.test(wanted) || wanted === host) break;
        host = wanted;
    }
    return {status, data: null};
}"""


def canonical(href):
    """'/slug/p/itm123?pid=ABC&lid=...' -> 'https://www.flipkart.com/slug/p/itm123?pid=ABC'."""
    parts = urlsplit(href)
    pid = parse_qs(parts.query).get("pid", [""])[0]
    return f"{HOME}{parts.path}" + (f"?pid={pid}" if pid else "")


def prepare(page, pincode):
    page.goto(HOME, wait_until="domcontentloaded", timeout=45000)
    return True


def search(page, query, limit, kind="laptop"):
    page.goto(f"{HOME}/search?q={quote_plus(query)}&sid={quote_plus(SIDS[kind])}", wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_selector('a[href*="/p/itm"]', timeout=15000)
    except Exception:
        if "recaptcha" in page.content().lower():
            raise StoreError("Flipkart asked for a CAPTCHA (it thinks this is a bot). Try again later.")
        return []
    hits, seen = [], set()
    for item in page.evaluate(_SEARCH_JS):
        url = canonical(item["href"])
        if url in seen or item["ad"]:
            continue
        # Its Tower PCs shelf pads every search with unrelated refurbished and assembled machines.
        if kind == "tower" and not relevant(item["title"], query):
            continue
        seen.add(url)
        hits.append(Hit(url=url, title=clean(item["title"])))
        if len(hits) >= limit:
            break
    return hits


def _find(node, wanted):
    """Every value stored under a key that starts with `wanted`, anywhere in the response."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key.startswith(wanted):
                yield value
            yield from _find(value, wanted)
    elif isinstance(node, list):
        for value in node:
            yield from _find(value, wanted)


def _label(cell, name):
    """The text of a label inside a widget cell; spec values arrive as one-item lists."""
    value = (cell.get(name) or {}).get("value") or {}
    text = value.get("text")
    if isinstance(text, list):
        text = ", ".join(str(part) for part in text)
    return clean(html.unescape(str(text))) if text not in (None, "") else ""


def _widget(data, view_type):
    for slot in data.get("RESPONSE", {}).get("slots", []):
        widget = slot.get("widget") or {}
        if widget.get("viewType") == view_type:
            return widget
    return {}


def parse_product(data, url, pincode):
    """Turn a page-data API response into a Product."""
    specs = {}
    for grid in _find(data, "rpd_specifications_grid_layout"):
        for cell in _find(grid, "value"):
            if isinstance(cell, dict) and "label_0" in cell and "label_1" in cell:
                name, value = _label(cell, "label_0"), _label(cell, "label_1")
                if name and value and name not in specs:
                    specs[name] = value

    title = ""
    for text in _find(_widget(data, "default_fk_pp_productTitle"), "prependingText"):
        title = clean(html.unescape(str(text)))
        break
    actions = _widget(data, "product-action")
    if not title:
        for cell in _find(actions, "label_random_to_get_title_in_child_header"):
            title = clean(str((cell.get("value") or {}).get("text") or ""))
            break
    if not title:
        raise StoreError("Flipkart's product data did not include a title (its layout may have changed).")

    price = next((p for p in _find(actions, "price") if isinstance(p, (int, float)) and p > 0), None)
    mrp = None
    for block in _find(_widget(data, "pp_pricing_price_summary"), "price_description"):
        mrp = rupees(_label(block.get("value") or {}, "label_1"))
        if not price:
            for variant in _find(block, "UNLOCKED"):
                price = rupees(((variant.get("value") or {}).get("text")))
                break
        break

    image = None
    for cell in _find(actions, "label_random_to_get_image_in_child_header"):
        image = (cell.get("value") or {}).get("text") or None
        break

    listing = {}
    try:
        listing = data["RESPONSE"]["pageData"]["pageContext"]["fdpEventTracking"]["events"]["psi"]["pls"] or {}
    except (KeyError, TypeError):
        pass
    in_stock = bool(price) and listing.get("availabilityStatus", "IN_STOCK") == "IN_STOCK" and listing.get("available", True)

    deliverable, note = None, None
    if pincode and listing and listing.get("unserviceabilityReason") != "NO_PINCODE":
        deliverable = bool(listing.get("serviceable"))
        if deliverable:
            for callout in _find(_widget(data, "default_fk_pp_delivery_widget"), "default_fk_pp_delivery_widget_delivery_callout"):
                when = _label(callout.get("value") or {}, "label_7")
                if when and "1970" not in when:
                    note = f"Delivery {when}"
                break

    return Product(
        url=url, title=title, image_url=image,
        price_inr=int(price) if price else None,
        mrp_inr=mrp if mrp and price and mrp >= price else None,
        in_stock=in_stock, raw_specs=specs, deliverable=deliverable, delivery_note=note,
    )


def _fetch(page, url, pincode):
    parts = urlsplit(url)
    body = {"pageUri": parts.path + (f"?{parts.query}" if parts.query else ""), "pageContext": {"fetchSeoData": True}}
    if pincode:
        body["locationContext"] = {"pincode": pincode}
    try:
        result = page.evaluate(_FETCH_JS, [body, page.evaluate("navigator.userAgent")])
    except Exception as error:
        raise StoreError("Flipkart's product data could not be fetched.") from error
    if result["status"] != 200 or not result["data"]:
        raise StoreError(f"Flipkart refused the product data request (HTTP {result['status']}).")
    return result["data"]


def read(page, url, pincode):
    product = parse_product(_fetch(page, url, pincode), url, pincode)
    if pincode and product.deliverable is None:
        # The first request of a session can come back before the PIN code has registered.
        product = parse_product(_fetch(page, url, pincode), url, pincode)
    return product
