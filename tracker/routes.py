"""Pages and form handlers."""
import re

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from . import hunts, listings, search
from .db import get_db, get_setting, set_setting

TABS = ("match", "near", "miss", "tracked")

bp = Blueprint("main", __name__)


def _hunt_or_404(hunt_id):
    hunt = hunts.get(hunt_id)
    if hunt is None:
        abort(404)
    return hunt


@bp.route("/")
def dashboard():
    all_hunts = hunts.all_hunts()
    return render_template(
        "dashboard.html",
        hunts=all_hunts,
        active=sum(1 for h in all_hunts if h["status"] == "active"),
        tracked=sum(h["tracked_count"] for h in all_hunts),
        interval=get_setting("check_interval_hours"),
    )


@bp.route("/hunts")
def hunt_list():
    hunts.purge()
    return render_template("hunts.html", hunts=hunts.all_hunts(), undo=session.pop("undo", None))


@bp.route("/hunts/new")
def hunt_new():
    return render_template("hunt_form.html", hunt=hunts.blank(), errors={})


@bp.route("/hunts", methods=["POST"])
def hunt_create():
    hunt, errors = hunts.parse_form(request.form)
    if errors:
        return render_template("hunt_form.html", hunt=hunt, errors=errors), 422
    hunt_id = hunts.create(hunt)
    flash(f"Saved “{hunt['name']}”.")
    return redirect(url_for("main.hunt_detail", hunt_id=hunt_id))


@bp.route("/hunts/<int:hunt_id>")
def hunt_detail(hunt_id):
    hunt = _hunt_or_404(hunt_id)
    found = listings.for_hunt(hunt)
    tab = request.args.get("tab")
    if tab not in TABS:
        # Open on the first tab that has something to review.
        tab = next((name for name in ("match", "near", "tracked", "miss") if found[name]), "match")
    return render_template(
        "hunt_detail.html", hunt=hunt, groups=hunts.filter_groups(hunt), found=found, tab=tab,
        job=search.job_for(hunt_id), searching=search.running(hunt_id), pincode=get_setting("delivery_pincode"),
    )


@bp.route("/hunts/<int:hunt_id>/search", methods=["POST"])
def hunt_search(hunt_id):
    hunt = _hunt_or_404(hunt_id)
    config = current_app.config
    started = search.start(hunt, {
        "database": config["DATABASE_PATH"],
        "channel": config["BROWSER_CHANNEL"],
        "headless": config["BROWSER_HEADLESS"],
        "limit": config["SEARCH_MAX_PER_STORE"],
        "pincode": get_setting("delivery_pincode"),
    })
    if not started:
        flash("None of this hunt's stores can be searched yet. Edit the hunt and pick Amazon or Flipkart.", "error")
    return redirect(url_for("main.hunt_detail", hunt_id=hunt_id))


@bp.route("/hunts/<int:hunt_id>/search/progress")
def hunt_search_progress(hunt_id):
    _hunt_or_404(hunt_id)
    job = search.job_for(hunt_id)
    if not job or job["finished"]:
        # Reload the whole page so the new listings appear.
        return "", 200, {"HX-Refresh": "true"}
    return render_template("_search_progress.html", hunt_id=hunt_id, job=job, searching=True)


@bp.route("/hunts/<int:hunt_id>/review", methods=["POST"])
def hunt_review(hunt_id):
    _hunt_or_404(hunt_id)
    shown = request.form.getlist("shown", type=int)
    ticked = set(request.form.getlist("track", type=int))
    tracked, hidden = listings.review(hunt_id, shown, ticked)
    parts = [f"Tracking {tracked} listing{'' if tracked == 1 else 's'}"] if tracked else []
    if hidden:
        parts.append(f"{'hid' if tracked else 'Hid'} {hidden} other{'' if hidden == 1 else 's'}")
    flash(", ".join(parts) + "." if parts else "Nothing was ticked.")
    return redirect(url_for("main.hunt_detail", hunt_id=hunt_id, tab="tracked" if tracked else request.form.get("tab")))


@bp.route("/hunts/<int:hunt_id>/listings/<int:listing_id>/<any(track, untrack, hide):action>", methods=["POST"])
def listing_state(hunt_id, listing_id, action):
    _hunt_or_404(hunt_id)
    state = {"track": "tracked", "untrack": "new", "hide": "ignored"}[action]
    if not listings.set_state(hunt_id, listing_id, state):
        abort(404)
    flash({"track": "Now tracking that listing.", "untrack": "Stopped tracking; its price history is kept.",
           "hide": "Hidden. It will not come back in later searches."}[action])
    return redirect(url_for("main.hunt_detail", hunt_id=hunt_id, tab=request.form.get("tab")))


@bp.route("/hunts/<int:hunt_id>/restore-hidden", methods=["POST"])
def hunt_restore_hidden(hunt_id):
    _hunt_or_404(hunt_id)
    restored = listings.restore_hidden(hunt_id)
    flash(f"Brought back {restored} hidden listing{'' if restored == 1 else 's'}.")
    return redirect(url_for("main.hunt_detail", hunt_id=hunt_id))


@bp.route("/hunts/<int:hunt_id>/edit")
def hunt_edit(hunt_id):
    return render_template("hunt_form.html", hunt=_hunt_or_404(hunt_id), errors={})


@bp.route("/hunts/<int:hunt_id>", methods=["POST"])
def hunt_update(hunt_id):
    existing = _hunt_or_404(hunt_id)
    hunt, errors = hunts.parse_form(request.form)
    if errors:
        return render_template("hunt_form.html", hunt={**existing, **hunt}, errors=errors), 422
    hunts.update(hunt_id, hunt)
    flash(f"Saved changes to “{hunt['name']}”.")
    return redirect(url_for("main.hunt_detail", hunt_id=hunt_id))


@bp.route("/hunts/<int:hunt_id>/<any(pause, resume):action>", methods=["POST"])
def hunt_status(hunt_id, action):
    _hunt_or_404(hunt_id)
    hunts.set_status(hunt_id, "paused" if action == "pause" else "active")
    if request.headers.get("HX-Request"):
        return render_template("_hunt_card.html", h=hunts.get(hunt_id))
    if request.form.get("next") == "detail":
        return redirect(url_for("main.hunt_detail", hunt_id=hunt_id))
    return redirect(url_for("main.hunt_list"))


@bp.route("/hunts/<int:hunt_id>/delete", methods=["POST"])
def hunt_delete(hunt_id):
    hunt = _hunt_or_404(hunt_id)
    hunts.delete(hunt_id)
    session["undo"] = {"id": hunt_id, "name": hunt["name"]}
    return redirect(url_for("main.hunt_list"))


@bp.route("/hunts/<int:hunt_id>/restore", methods=["POST"])
def hunt_restore(hunt_id):
    if hunts.restore(hunt_id):
        flash("Hunt restored.")
    else:
        flash("Too late to undo: that hunt has already been removed.", "error")
    return redirect(url_for("main.hunt_list"))


@bp.route("/tracked")
def tracked():
    return render_template("tracked.html")


@bp.route("/settings")
def settings():
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    return render_template("settings.html", settings={row["key"]: row["value"] for row in rows}, error=None)


@bp.route("/settings/delivery", methods=["POST"])
def settings_delivery():
    pincode = re.sub(r"\s", "", request.form.get("delivery_pincode", ""))
    if pincode and not re.fullmatch(r"[1-9]\d{5}", pincode):
        rows = get_db().execute("SELECT key, value FROM settings").fetchall()
        saved = {row["key"]: row["value"] for row in rows}
        return render_template(
            "settings.html", settings={**saved, "delivery_pincode": pincode},
            error="A PIN code is 6 digits, like 560001.",
        ), 422
    set_setting("delivery_pincode", pincode)
    flash(f"Delivery will be checked for PIN code {pincode} from the next search." if pincode
          else "Delivery PIN code cleared. Delivery will not be checked.")
    return redirect(url_for("main.settings"))
