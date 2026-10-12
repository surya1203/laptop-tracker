"""Runs a hunt's store search in the background and reports progress.

One thread per store, each with its own browser, a few at a time. Progress lives in memory
(JOBS), which the results page polls; listings are written to the database as they are read.
"""
import math
import random
import threading
import time

from . import listings, specs
from .browser import open_page
from .db import connect, now
from .stores import STORES, sells
from .stores.base import StoreError

MAX_QUERIES = 6
# Stop reading a store after this many product pages fail in a row: it has likely started blocking.
MAX_FAILURES_IN_A_ROW = 3
# Browsers open at once; the remaining stores wait their turn.
MAX_BROWSERS = 4

JOBS = {}  # hunt id -> the latest job for that hunt
_lock = threading.Lock()


def queries(hunt, only_brands=None):
    """Search phrases for a hunt: one per brand and GPU combination, kept loose so stores return enough.

    A brand's own store passes `only_brands`, so it is not asked about its competitors.
    """
    brands = hunt["brands"] or [None]
    if only_brands:
        wanted = [name.lower() for name in only_brands]
        brands = [brand for brand in brands if brand and brand.lower() in wanted] or list(only_brands)[:1]
    gpus = hunt["gpu_models"] or [None]
    kind = hunt.get("kind") or "laptop"
    phrases = []
    for brand in brands:
        for gpu in gpus:
            parts = [brand, hunt["series"], gpu]
            if not hunt["series"] and not gpu:
                parts += [hunt["cpu_family"], hunt["gpu_brand"] if hunt["gpu_brand"] != "Apple" else None]
            phrase = " ".join(part for part in parts if part)
            if kind == "tower":
                phrase = f"{phrase} desktop"
            elif "macbook" not in phrase.lower():
                phrase = f"{phrase} laptop"
            if phrase not in phrases:
                phrases.append(phrase)
    return phrases[:MAX_QUERIES]


def _pause(low=1.5, high=4.0):
    time.sleep(random.uniform(low, high))


def _run_store(store, state, hunt, options, turn):
    phrases = queries(hunt, getattr(store, "BRANDS", None))
    conn = connect(options["database"])
    try:
        with turn, open_page(options["channel"], options["headless"]) as page:
            state["phase"] = "searching"
            pincode = options["pincode"]
            if not store.prepare(page, pincode):
                state["note"] = f"would not accept PIN code {pincode}, so delivery was not checked"
                pincode = None

            skip = listings.ignored_urls(conn, hunt["id"], store.KEY)
            per_phrase = math.ceil(options["limit"] / len(phrases))
            hits = {}
            for phrase in phrases:
                for hit in store.search(page, phrase, per_phrase, hunt.get("kind") or "laptop"):
                    if hit.url not in skip:
                        hits.setdefault(hit.url, hit)
                state["found"] = len(hits)
                _pause()
            hits = list(hits.values())[:options["limit"]]
            state["found"] = len(hits)

            state["phase"] = "reading"
            failures = 0
            for hit in hits:
                try:
                    product = store.read(page, hit.url, pincode)
                except Exception as error:
                    failures += 1
                    state["unread"] += 1
                    if failures >= MAX_FAILURES_IN_A_ROW:
                        raise StoreError(str(error) if isinstance(error, StoreError) else
                                         f"{store.LABEL} stopped answering part-way through.") from error
                else:
                    failures = 0
                    typed = specs.normalise(product.title, product.raw_specs)
                    if listings.save(conn, hunt["id"], store.KEY, product, typed, pincode):
                        state["new"] += 1
                state["checked"] += 1
                _pause()
        state["phase"] = "done"
    except StoreError as error:
        state.update(phase="failed", error=str(error))
    except Exception as error:
        message = str(error).splitlines()[0] if str(error) else type(error).__name__
        state.update(phase="failed", error=message[:200])
    finally:
        conn.close()


def _run(job, hunt, options):
    turn = threading.BoundedSemaphore(MAX_BROWSERS)
    threads = [
        threading.Thread(target=_run_store, args=(STORES[key], state, hunt, options, turn), daemon=True)
        for key, state in job["stores"].items()
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    conn = connect(options["database"])
    try:
        conn.execute("UPDATE hunts SET last_searched_at = ? WHERE id = ?", (now(), hunt["id"]))
        conn.commit()
    finally:
        conn.close()
    job["problems"] = any(state["phase"] == "failed" or state["note"] for state in job["stores"].values())
    job["finished"] = True


def start(hunt, options):
    """Begin a search unless one is already running for this hunt. Returns False if none could start."""
    keys = [key for key in hunt["retailers"] if key in STORES and sells(STORES[key], hunt["brands"], hunt.get("kind") or "laptop")]
    if not keys:
        return False
    with _lock:
        if running(hunt["id"]):
            return True
        job = {
            "finished": False,
            "problems": False,  # set at the end: a store failed, or refused the PIN code
            "stores": {
                key: {"label": STORES[key].LABEL, "phase": "queued", "found": 0, "checked": 0,
                      "new": 0, "unread": 0, "error": None, "note": None}
                for key in keys
            },
        }
        JOBS[hunt["id"]] = job
    threading.Thread(target=_run, args=(job, hunt, options), daemon=True).start()
    return True


def job_for(hunt_id):
    return JOBS.get(hunt_id)


def running(hunt_id):
    job = JOBS.get(hunt_id)
    return bool(job) and not job["finished"]
