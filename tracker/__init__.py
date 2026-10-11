"""Laptop Tracker: describe a laptop, preview store listings, track prices, get alerts."""
from datetime import datetime

from flask import Flask

from . import catalog, db, hunts
from .config import Config


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config.update(config or {})

    db.init_db(app)
    app.teardown_appcontext(db.close_db)

    app.jinja_env.filters.update(inr=hunts.inr, num=hunts.num, size=hunts.size, shortdate=_shortdate)
    app.jinja_env.globals.update(catalog=catalog, hunt_chips=hunts.chips, undo_seconds=hunts.UNDO_SECONDS)

    from .routes import bp
    app.register_blueprint(bp)
    return app


def _shortdate(iso):
    """'2026-10-10T08:30:00+00:00' -> '10 Oct 2026' in local time."""
    stamp = datetime.fromisoformat(iso).astimezone()
    return f"{stamp.day} {stamp:%b %Y}"
