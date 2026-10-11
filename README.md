# Laptop Tracker

Describe the laptop you want, preview what Indian stores have, pick the listings to track, and get told when one hits a new low. The full design is in [PLAN.md](PLAN.md).

## Status

Built in five phases (see "Build order" in the plan). **Phase 1 is done; nothing searches stores, tracks prices or sends alerts yet.**

| Phase | What | State |
| --- | --- | --- |
| 1 | Project layout, database, design system, filter form, edit/pause/delete hunts | Done |
| 2 | Search and preview on Amazon + Flipkart | Not started |
| 3 | Price history, scheduler, Tracked page | Not started |
| 4 | Alerts (email, WhatsApp) | Not started |
| 5 | More stores, add-by-URL, dashboard, mobile pass | Not started |

## Run it

```
pip install -r requirements.txt
python run.py
```

Then open http://127.0.0.1:5000. The database (`tracker.db`) is created on first start.

Configuration is read from `.env`; every value is optional. See `.env.example` for the list (`DATABASE_PATH`, `HOST`, `PORT`, `SECRET_KEY`, `FLASK_DEBUG`).

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
  migrate.py        one-time import of saved searches from the old database
  routes.py         pages and form handlers
  templates/        Jinja pages (Tailwind, HTMX)
  static/app.js     cascading dropdowns, active-filter chips, toasts
_old/               the pre-rebuild app, kept for reference; not used at runtime
```

`_old/tracker.db` is read once, on first start, to import the saved searches. After that the folder can be deleted.
