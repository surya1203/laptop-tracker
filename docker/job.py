"""One round of scheduled work, then exit: python job.py

The app's own schedule is a thread that only runs while the website is open. In containers the
website runs with that switched off, and a timer starts this instead every few hours, so nothing
has to stay busy between rounds. One round is what the thread does in one wake-up: the price
check if it is due, the search for new listings if that is due, the update, and a few lookups
of earlier prices. `--force` checks prices even if the interval has not passed.
"""
import argparse
import os
import sys
from datetime import datetime, timezone

os.environ["SCHEDULER"] = "0"  # this process is the schedule; it must not start the background one as well

from tracker import backfill, checker, create_app, scheduler  # noqa: E402
from tracker.db import connect, now  # noqa: E402


def run_round(app, options, force=False):
    """Returns whether prices were checked. Mirrors one pass of scheduler._loop."""
    conn = connect(options["database"])
    try:
        due = (force or scheduler.next_check(conn) <= datetime.now(timezone.utc)) and bool(checker.due_listings(conn))
        # Not if another container, or a copy of the app, took this round moments ago.
        due = due and scheduler.claim_round(conn)
        search_at = scheduler.next_search(conn)
    finally:
        conn.close()
    began = now()
    checked = due and checker.run(options)
    if search_at and search_at <= datetime.now(timezone.utc):
        scheduler.search_hunts(app, options)
    if checked:
        scheduler.send_update(app, options, began)
    return bool(checked)


def main():
    parser = argparse.ArgumentParser(description="Run one round of price checks and searches, then exit.")
    parser.add_argument("--force", action="store_true", help="check prices now, even if the interval has not passed")
    args = parser.parse_args()
    app = create_app()
    checked = run_round(app, scheduler.check_options(app.config), force=args.force)
    print("Prices checked." if checked else "No price check was due.")
    try:
        backfill.run_pending(app.config["DATABASE_PATH"])
    except Exception as error:
        print(f"Earlier prices could not be imported: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
