"""Laptop Tracker: describe a laptop, preview store listings, track prices, get alerts."""
from datetime import datetime

from flask import Flask

from . import catalog, db, hunts, scheduler
from .config import Config


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config.update(config or {})

    db.init_db(app)
    app.teardown_appcontext(db.close_db)

    app.jinja_env.filters.update(inr=hunts.inr, num=hunts.num, size=hunts.size, shortdate=_shortdate, when=_when)
    app.jinja_env.globals.update(catalog=catalog, hunt_chips=hunts.chips, undo_seconds=hunts.UNDO_SECONDS)

    from .routes import bp
    app.register_blueprint(bp)
    scheduler.start(app)
    return app


def _shortdate(iso):
    """'2026-10-10T08:30:00+00:00' -> '10 Oct 2026' in local time."""
    stamp = datetime.fromisoformat(iso).astimezone()
    return f"{stamp.day} {stamp:%b %Y}"


def _when(iso):
    """A check time the way you would say it: 'today 14:05', 'yesterday 09:30', '8 Oct 21:10'."""
    if not iso:
        return "never"
    stamp = datetime.fromisoformat(iso).astimezone()
    days = (datetime.now().astimezone().date() - stamp.date()).days
    day = {0: "today", 1: "yesterday", -1: "tomorrow"}.get(days, f"{stamp.day} {stamp:%b}")
    return f"{day} {stamp:%H:%M}"
