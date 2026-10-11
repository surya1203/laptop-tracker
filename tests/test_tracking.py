"""Price history, alert rules, quiet hours and the check schedule."""
import sqlite3
from datetime import datetime, timedelta, timezone

from werkzeug.datastructures import MultiDict

from tracker import alerts, history, hunts, scheduler

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def _point(days_ago, price, in_stock=1, mrp=None):
    stamp = (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds")
    return {"price_inr": price, "mrp_inr": mrp, "in_stock": in_stock, "checked_at": stamp}


def _rules(**changes):
    hunt = {"alert_new_low": 1, "alert_back_in_stock": 1, "alert_target_inr": None, "alert_drop_pct": None}
    hunt.update(changes)
    return hunt


def test_lows_and_change_come_from_the_history():
    found = history.summary([_point(60, 180000), _point(20, 200000), _point(1, 210000), _point(0, 195000)], NOW)
    assert (found["price_inr"], found["previous_inr"], found["change_inr"]) == (195000, 210000, -15000)
    assert (found["low_inr"], found["low_30_inr"], found["above_low_inr"]) == (180000, 195000, 15000)
    assert not found["at_low"] and found["checks"] == 4 and found["spark"]


def test_an_out_of_stock_check_never_counts_as_a_low():
    found = history.summary([_point(3, 200000), _point(2, 150000, in_stock=0), _point(0, 190000)], NOW)
    assert (found["low_inr"], found["previous_inr"], found["at_low"]) == (190000, 200000, True)


def test_one_check_is_not_yet_a_low_or_a_chart():
    found = history.summary([_point(0, 200000)], NOW)
    assert (found["low_inr"], found["at_low"], found["change_inr"], found["spark"]) == (200000, False, None, None)
    assert history.summary([], NOW)["price_inr"] is None


def test_new_low_alert():
    assert [rule for rule, _ in alerts.triggered(_rules(), [_point(2, 200000), _point(1, 205000), _point(0, 199000)])] == ["new_low"]
    assert alerts.triggered(_rules(), [_point(1, 200000), _point(0, 200000)]) == []
    assert alerts.triggered(_rules(alert_new_low=0), [_point(1, 200000), _point(0, 190000)]) == []


def test_the_first_check_of_a_listing_raises_nothing():
    assert alerts.triggered(_rules(alert_target_inr=250000), [_point(0, 200000)]) == []


def test_target_alert_fires_on_crossing_not_while_staying_under():
    rules = _rules(alert_new_low=0, alert_target_inr=190000)
    assert [rule for rule, _ in alerts.triggered(rules, [_point(1, 200000), _point(0, 189990)])] == ["target"]
    assert alerts.triggered(rules, [_point(2, 200000), _point(1, 189990), _point(0, 189990)]) == []


def test_drop_alert_compares_with_the_previous_check():
    rules = _rules(alert_new_low=0, alert_drop_pct=5)
    assert [rule for rule, _ in alerts.triggered(rules, [_point(2, 150000), _point(1, 200000), _point(0, 190000)])] == ["drop"]
    assert alerts.triggered(rules, [_point(1, 200000), _point(0, 195000)]) == []


def test_back_in_stock_alert():
    points = [_point(2, 200000), _point(1, 200000, in_stock=0), _point(0, 200000)]
    assert [rule for rule, _ in alerts.triggered(_rules(), points)] == ["back_in_stock"]
    assert alerts.triggered(_rules(), points[:2]) == []  # going out of stock is not news


def test_quiet_hours_can_wrap_past_midnight():
    assert alerts.in_quiet_hours("22:00", "07:00", datetime(2026, 10, 11, 23, 30))
    assert alerts.in_quiet_hours("22:00", "07:00", datetime(2026, 10, 12, 6, 59))
    assert not alerts.in_quiet_hours("22:00", "07:00", datetime(2026, 10, 12, 7, 0))
    assert alerts.in_quiet_hours("13:00", "15:00", datetime(2026, 10, 12, 14, 0))
    assert not alerts.in_quiet_hours("", "", datetime(2026, 10, 12, 14, 0))


def test_rupees_use_indian_grouping():
    assert (alerts.rupees(189990), alerts.rupees(999), alerts.rupees(12345678)) == ("₹1,89,990", "₹999", "₹1,23,45,678")


def _settings(**values):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany("INSERT INTO settings VALUES (?, ?)", values.items())
    return conn


def test_next_check_follows_the_chosen_interval():
    last = "2026-10-11T06:00:00+00:00"
    assert scheduler.next_check(_settings(check_interval_hours="3", last_check_at=last)) == datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
    assert scheduler.next_check(_settings(check_interval_hours="1", last_check_at=last)) == datetime(2026, 10, 11, 7, 0, tzinfo=timezone.utc)
    # An interval that is not offered falls back to the default.
    assert scheduler.interval_hours(_settings(check_interval_hours="5")) == scheduler.DEFAULT_INTERVAL
    assert scheduler.next_check(_settings()) <= datetime.now(timezone.utc)
    assert {1, 3, 6, 12} <= set(scheduler.INTERVALS)


def test_hunt_form_reads_alert_rules():
    form = MultiDict([("name", "Test"), ("retailers", "amazon"), ("alert_new_low", "1"),
                      ("alert_target_inr", "2,25,000"), ("alert_drop_pct", "5")])
    hunt, errors = hunts.parse_form(form)
    assert not errors
    assert (hunt["alert_new_low"], hunt["alert_back_in_stock"], hunt["alert_target_inr"], hunt["alert_drop_pct"]) == (1, 0, 225000, 5)
    assert hunts.blank()["alert_new_low"] == 1
