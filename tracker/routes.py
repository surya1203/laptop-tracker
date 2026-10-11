"""Pages and form handlers."""
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from . import hunts
from .db import get_db, get_setting

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
    return render_template("hunt_detail.html", hunt=hunt, groups=hunts.filter_groups(hunt))


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
    return render_template("settings.html", settings={row["key"]: row["value"] for row in rows})
