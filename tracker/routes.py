"""Pages and form handlers."""
import json
import re
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from . import alerts, checker, hunts, listings, scheduler, search
from .db import get_db, get_setting, set_setting

TABS = ("match", "near", "miss", "tracked")

bp = Blueprint("main", __name__)


def _hunt_or_404(hunt_id):
    hunt = hunts.get(hunt_id)
    if hunt is None:
        abort(404)
    return hunt


def _schedule():
    """What the pages say about price checks: how often, the last one, the next one."""
    db = get_db()
    try:
        result = json.loads(get_setting("last_check_result") or "{}")
    except ValueError:
        result = {}
    due = scheduler.next_check(db)
    return {
        "interval": scheduler.interval_hours(db),
        "last_at": get_setting("last_check_at"),
        "result": result,
        "next_at": max(due, datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "enabled": current_app.config["SCHEDULER"],
        "running": checker.RUN["running"],
    }


@bp.route("/")
def dashboard():
    all_hunts = hunts.all_hunts()
    groups = listings.tracked()
    tracked = [listing for group in groups for listing in group["listings"]]
    drops = sorted((l for l in tracked if l["change_inr"] and l["change_inr"] < 0), key=lambda l: l["change_inr"])
    return render_template(
        "dashboard.html",
        hunts=all_hunts,
        active=sum(1 for h in all_hunts if h["status"] == "active"),
        tracked=len(tracked),
        at_low=[l for l in tracked if l["at_low"]],
        drops=drops[:5],
        feed=alerts.recent(get_db(), 10),
        schedule=_schedule(),
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
        flash("None of this hunt's stores sell its brands. Edit the hunt and tick another store.", "error")
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
    groups = listings.tracked()
    return render_template(
        "tracked.html", groups=groups, count=sum(len(group["listings"]) for group in groups),
        schedule=_schedule(), run=checker.RUN, pincode=get_setting("delivery_pincode"),
    )


@bp.route("/tracked/check", methods=["POST"])
def tracked_check():
    if not checker.due_listings(get_db()):
        flash("There is nothing to check: no tracked listings on an active hunt.", "error")
    elif not checker.start(scheduler.check_options(current_app.config)):
        flash("A price check is already running.")
    return redirect(url_for("main.tracked"))


@bp.route("/tracked/check/progress")
def tracked_check_progress():
    if not checker.RUN["running"]:
        # Reload the whole page so the new prices appear.
        return "", 200, {"HX-Refresh": "true"}
    return render_template("_check_progress.html", run=checker.RUN)


@bp.route("/tracked/<int:listing_id>/untrack", methods=["POST"])
def tracked_untrack(listing_id):
    row = get_db().execute("SELECT hunt_id FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if not row or not listings.set_state(row["hunt_id"], listing_id, "new"):
        abort(404)
    flash("Stopped tracking; its price history is kept.")
    return redirect(url_for("main.tracked"))


def _settings_page(error=None, status=200, **typed):
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    config = current_app.config
    return render_template(
        "settings.html", settings={**{row["key"]: row["value"] for row in rows}, **typed}, error=error,
        schedule=_schedule(), intervals=scheduler.INTERVALS,
        email_ready=bool(config["SENDER_EMAIL"] and config["GMAIL_APP_PASSWORD"]),
        whatsapp_ready=bool(config["CALLMEBOT_API_KEY"]), cooldown=alerts.DEFAULT_COOLDOWN_HOURS,
    ), status


@bp.route("/settings")
def settings():
    return _settings_page()


@bp.route("/settings/checks", methods=["POST"])
def settings_checks():
    hours = request.form.get("check_interval_hours", type=int)
    if hours not in scheduler.INTERVALS:
        abort(400)
    set_setting("check_interval_hours", str(hours))
    flash(f"Prices will be checked every {hours} hour{'' if hours == 1 else 's'}.")
    return redirect(url_for("main.settings"))


@bp.route("/settings/alerts", methods=["POST"])
def settings_alerts():
    form = {key: " ".join(request.form.get(key, "").split()) for key in
            ("notify_email", "notify_whatsapp", "quiet_start", "quiet_end", "alert_cooldown_hours")}
    form["notify_whatsapp"] = re.sub(r"[\s-]", "", form["notify_whatsapp"])
    problem = None
    if form["notify_email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", form["notify_email"]):
        problem = "That email address does not look right."
    elif form["notify_whatsapp"] and not re.fullmatch(r"\+\d{10,15}", form["notify_whatsapp"]):
        problem = "Give the WhatsApp number with its country code, like +919876543210."
    elif bool(form["quiet_start"]) != bool(form["quiet_end"]):
        problem = "Quiet hours need both a start and an end time, or neither."
    elif any(value and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value) for value in (form["quiet_start"], form["quiet_end"])):
        problem = "Quiet hours are times like 22:00."
    elif form["alert_cooldown_hours"] and not re.fullmatch(r"[1-9]\d{0,2}", form["alert_cooldown_hours"]):
        problem = "The repeat gap is a whole number of hours, 1 to 999."
    if problem:
        return _settings_page(alert_error=problem, status=422, **form)
    for key, value in form.items():
        set_setting(key, value)
    flash("Alert settings saved.")
    return redirect(url_for("main.settings"))


@bp.route("/settings/test/<any(email, whatsapp):channel>", methods=["POST"])
def settings_test(channel):
    mail = scheduler.check_options(current_app.config)["mail"]
    body = "This is a test alert from Laptop Tracker. If you can read it, this channel works."
    try:
        if channel == "email":
            address = get_setting("notify_email")
            if not address:
                raise RuntimeError("Save an email address first.")
            alerts.send_email(mail, address, "Laptop Tracker test alert", body)
        else:
            address = get_setting("notify_whatsapp")
            if not address:
                raise RuntimeError("Save a WhatsApp number first.")
            alerts.send_whatsapp(mail, address, body)
    except Exception as error:
        flash(f"Test not sent: {str(error).splitlines()[0][:200]}", "error")
    else:
        flash(f"Test alert sent to {address}.")
    return redirect(url_for("main.settings"))


@bp.route("/settings/delivery", methods=["POST"])
def settings_delivery():
    pincode = re.sub(r"\s", "", request.form.get("delivery_pincode", ""))
    if pincode and not re.fullmatch(r"[1-9]\d{5}", pincode):
        return _settings_page(error="A PIN code is 6 digits, like 560001.", status=422, delivery_pincode=pincode)
    set_setting("delivery_pincode", pincode)
    flash(f"Delivery will be checked for PIN code {pincode} from the next search." if pincode
          else "Delivery PIN code cleared. Delivery will not be checked.")
    return redirect(url_for("main.settings"))
