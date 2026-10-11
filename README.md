# Laptop Tracker

Describe the laptop you want, preview what Indian stores have, pick the listings to track, and get told when one hits a new low. The full design is in [PLAN.md](PLAN.md).

## Status

Built in five phases (see "Build order" in the plan). **Phases 1 and 2 are done: a hunt can be searched on Amazon and Flipkart and its listings reviewed and marked as tracked. Nothing re-checks prices on a schedule or sends alerts yet.**

| Phase | What | State |
| --- | --- | --- |
| 1 | Project layout, database, design system, filter form, edit/pause/delete hunts | Done |
| 2 | Search and preview on Amazon + Flipkart, delivery check by PIN code | Done |
| 3 | Price history, scheduler, Tracked page | Not started |
| 4 | Alerts (email, WhatsApp) | Not started |
| 5 | More stores, add-by-URL, dashboard, mobile pass | Not started |

## Run it

```
pip install -r requirements.txt
python run.py
```

Then open http://127.0.0.1:5000. The database (`tracker.db`) is created on first start.

Configuration is read from `.env`; every value is optional. See `.env.example` for the list (`DATABASE_PATH`, `HOST`, `PORT`, `SECRET_KEY`, `FLASK_DEBUG`, `BROWSER_CHANNEL`, `BROWSER_HEADLESS`, `SEARCH_MAX_PER_STORE`).

## Searching stores

Open a hunt and press **Search now**. Each store is driven in its own background browser: it runs the hunt's search phrases, opens every result's product page, reads the spec table, and files the listing under **Matches** (every filter met), **Near misses** (at most one filter failed, or the page left something unsaid) or **Others**. Tick the ones to follow and press **Track selected**; the unticked ones on that tab are hidden from later searches, and can be brought back from the link under the results.

- **Browser.** The search uses Playwright. With no `BROWSER_CHANNEL` set it uses Playwright's own Chromium if installed (`playwright install chromium`), otherwise the Edge or Chrome already on the PC. It runs without a window; set `BROWSER_HEADLESS=0` to watch it, which helps if a store starts blocking.
- **Delivery.** Set a PIN code under Settings (optional) and each search also records whether a listing can be delivered there. Blank means the check is skipped.
- **Speed.** Pages are opened one at a time with a 1.5 to 4 second pause, so 24 listings per store (the default cap) takes about two minutes.
- **When a store changes its pages.** Each store's parsing is one file in `tracker/stores/`. A store that cannot be read shows "Store check failed" with the reason; the other store's results are still saved.

## Tests

```
python -m pytest tests
```

Covers the spec normaliser and filter matching. The store scrapers are checked by running a search.

## Layout

```
run.py              start the app
tracker/
  __init__.py       app factory
  config.py         settings from .env
  db.py             SQLite connection, first-run setup
  schema.sql        the five tables: hunts, listings, price_points, alerts, settings
  catalog.py        the fixed choices behind each filter (brands, CPU families, GPU models, ...)
  hunts.py          hunt form parsing, storage, display text
  search.py         background search job and its progress
  browser.py        starts the browser the scrapers drive
  stores/           one module per store (amazon.py, flipkart.py) behind the interface in base.py
  specs.py          spec normaliser: store spec table + title -> typed values
  matching.py       compares a listing's specs with a hunt's filters
  listings.py       found listings: storage, grouping, track / hide
  migrate.py        one-time import of saved searches from the old database
  routes.py         pages and form handlers
  templates/        Jinja pages (Tailwind, HTMX)
  static/app.js     cascading dropdowns, active-filter chips, review bar, toasts
tests/              unit tests
_old/               the pre-rebuild app, kept for reference; not used at runtime
```

`_old/tracker.db` is read once, on first start, to import the saved searches. After that the folder can be deleted.
