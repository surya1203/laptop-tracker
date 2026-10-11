# Laptop Tracker

Describe the laptop you want, preview what Indian stores have, pick the listings to track, and get told when one hits a new low. The full design is in [PLAN.md](PLAN.md).

> **Disclaimer.** This project was vibecoded: the code was written with an AI coding assistant (Claude Code). The developer, Surya Giri, built it for educational and personal use, and made the executive decisions throughout: what to build, which stores to cover, how tracking and alerts should behave, and what to change after trying it. It reads public store pages for one person's own price tracking; treat it as a personal learning project, not a supported product.

## Status

Built in five phases (see "Build order" in the plan). **Phases 1 to 4 are done, and the extra stores from phase 5 were brought forward: hunts are searched on eleven stores, tracked listings are re-checked on a schedule, and price alerts go to the Dashboard, email and WhatsApp.** Left: add-by-URL, the mobile pass, and the items under "Not built yet".

| Phase | What | State |
| --- | --- | --- |
| 1 | Project layout, database, design system, filter form, edit/pause/delete hunts | Done |
| 2 | Search and preview, delivery check by PIN code | Done |
| 3 | Price history, scheduler, Tracked page | Done |
| 4 | Alerts (in-app feed, email, WhatsApp) | Done; "new match" rule not built |
| 5 | More stores (done early, Oct 11), add-by-URL, dashboard, mobile pass | Stores done; rest not started |

## Run it

```
pip install -r requirements.txt
python run.py
```

Then open http://127.0.0.1:5000. The database (`tracker.db`) is created on first start.

Configuration is read from `.env`; every value is optional. See `.env.example` for the list (`DATABASE_PATH`, `HOST`, `PORT`, `SECRET_KEY`, `FLASK_DEBUG`, `BROWSER_CHANNEL`, `BROWSER_HEADLESS`, `SEARCH_MAX_PER_STORE`).

## Searching stores

Open a hunt and press **Search now**. Each store is driven in its own background browser: it runs the hunt's search phrases, opens every result's product page, reads the spec table, and files the listing under **Matches** (every filter met), **Near misses** (at most one filter failed, or the page left something unsaid) or **Others**. Tick the ones to follow and press **Track selected**; the unticked ones on that tab are hidden from later searches, and can be brought back from the link under the results.

### Stores

| Store | Site searched | Delivery check by PIN code |
| --- | --- | --- |
| Amazon | amazon.in | Yes |
| Flipkart | flipkart.com | Yes |
| Croma | croma.com | Yes |
| Vijay Sales | vijaysales.com | Yes |
| Reliance Digital | reliancedigital.in | No (its check needs requests signed by the site) |
| Lenovo Store | lenovo.com/in | No |
| ASUS Store | asus.com/in/store (sells through in.store.asus.com) | No |
| Dell Store | dellstore.com (where dell.com/en-in sends shoppers) | No |
| Acer Store | store.acer.com/en-in | No |
| Apple Store | apple.com/in | No |
| Samsung Store | samsung.com/in | No |

A brand's own store is searched only when the hunt includes that brand or has no brand filter. Not covered: HP's store (hp.com/in-en/shop) turns automated browsers away, and MSI and Gigabyte do not sell online in India themselves; their laptops are still found at the five multi-brand stores.

Notes on individual stores:

- **Lenovo** lists "customisable" models; the price read is for the starting configuration.
- **ASUS** has a small catalogue and no working search, so its whole laptop listing is read and the closest models are opened.
- **Acer** blocks its product pages, so price and stock are read from its search results, and specs come from the product name.
- **Samsung** publishes no spec sheet in its listing, so only processor, memory, storage and screen size are known.

- **Browser.** The search uses Playwright. With no `BROWSER_CHANNEL` set it uses Playwright's own Chromium if installed (`playwright install chromium`), otherwise the Edge or Chrome already on the PC. It runs without a window; set `BROWSER_HEADLESS=0` to watch it, which helps if a store starts blocking.
- **Delivery.** Set a PIN code under Settings (optional) and each search also records whether a listing can be delivered there. Blank means the check is skipped.
- **Speed.** At most four stores run at once and pages are opened one at a time with a 1.5 to 4 second pause. With the default cap of 24 listings per store, a search of all eleven stores takes several minutes.
- **When a store changes its pages.** Each store's parsing is one file in `tracker/stores/`. A store that cannot be read shows "Store check failed" with the reason; the other store's results are still saved.

## Tracking prices

Listings you tick in a hunt appear on the **Tracked** page. The same model found at several stores is grouped, cheapest first. Each listing shows its current price, the change since the previous check, its all-time and 30-day lows, and a small price chart.

- **Schedule.** While the app is running, every tracked listing on an active hunt is re-checked every 1, 3, 6, 12 or 24 hours (Settings; default 6). The time of the last check is kept in the database, so restarting does not reset the clock; a check that became due while the app was closed runs about half a minute after it starts. **Check prices now** on the Tracked page runs one straight away. `SCHEDULER=0` in `.env` turns the automatic checks off.
- **Lows** come from this tracker's own checks, so they start the day a listing was first found. A check that found the listing out of stock is recorded but never counts as a low.
- **Paused hunts** are not checked and raise no alerts.
- Scheduled checks re-read tracked listings only. Finding new listings still means pressing **Search now** on the hunt.

## Alerts

Each hunt has an Alerts panel in its form with four rules: a new all-time low (on by default), back in stock (on by default), price at or under a target, and a fall of at least X% since the previous check. They apply to the listings tracked from that hunt.

Every alert is listed on the Dashboard. To also get them by email or WhatsApp, fill in Settings > Alerts and press the test buttons:

- **Email** needs a Gmail address to send from and an app password for it (Gmail refuses an app signing in with the normal password; the page links to where Google issues one). Alerts go to that same address unless you give another.
- **WhatsApp** needs your number and a key from the free CallMeBot service (the page links to its steps).

These are kept in the tracker's database (`tracker.db`, which is not uploaded to GitHub), as plain text.

The same rule does not fire again for the same listing within 24 hours (changeable in Settings). During quiet hours, if set, alerts show on the Dashboard only and are not sent later.

## Not built yet

- The "new match" alert (a new listing appearing for a hunt), which needs hunts to be re-searched on a schedule.
- A full price-history chart per listing (the Tracked page has a sparkline), and deleting a listing with its history.
- Telegram, add-by-URL, "Clear all tracking", and protection against forged form posts (keep `HOST` on 127.0.0.1 until that exists).

## Tests

```
python -m pytest tests
```

Covers the spec normaliser, filter matching, price history, alert rules, the schedule, and the parts of the store modules that work without a browser. Reading the live stores is checked by running a search or a price check.

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
  stores/           one module per store behind the interface in base.py; magento.py is shared by Dell and ASUS
  specs.py          spec normaliser: store spec table + title -> typed values
  matching.py       compares a listing's specs with a hunt's filters
  listings.py       found listings: storage, grouping, track / hide, the Tracked page's groups
  history.py        lows, change since the last check and the sparkline, from a listing's price points
  checker.py        background re-check of every tracked listing
  scheduler.py      starts a check when the chosen interval has passed
  alerts.py         alert rules, cooldown, quiet hours, email and WhatsApp sending, the feed
  migrate.py        one-time import of saved searches from the old database
  routes.py         pages and form handlers
  templates/        Jinja pages (Tailwind, HTMX)
  static/app.js     cascading dropdowns, active-filter chips, review bar, toasts
tests/              unit tests
_old/               the pre-rebuild app, kept for reference; not used at runtime
```

`_old/tracker.db` is read once, on first start, to import the saved searches. After that the folder can be deleted.
