"""Tests for the My-usage month selector and its per-week cost stats.

The personal page selects a *month* (not a single week) and shows weekly cost
stats for each ISO week in that month, up to the latest week with data. A week
is attributed to the month its Monday falls in, so a week that straddles a
month boundary (e.g. 2026-W27, 29 Jun – 5 Jul) belongs to June.
"""

from pytest import approx

from app.main.services import ai_credits as ac


def _rows(make_record):
    # alice spans three months; 2026-W27 straddles Jun/Jul (Monday 29 Jun -> Jun).
    return [
        make_record("2026-05-25", "alice", 10.0),   # 2026-W22, month 2026-05
        make_record("2026-06-01", "alice", 20.0),   # 2026-W23, month 2026-06
        make_record("2026-06-08", "alice", 30.0),   # 2026-W24, month 2026-06
        make_record("2026-06-29", "alice", 40.0),   # 2026-W27, month 2026-06
        make_record("2026-07-01", "alice", 5.0),    # 2026-W27 (same week as 29 Jun)
        make_record("2026-07-06", "alice", 7.0),    # 2026-W28, month 2026-07
    ]


def test_months_selector_defaults_to_latest_month(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month")
    assert v["months"] == ["2026-05", "2026-06", "2026-07"]
    assert v["month"] == "2026-07"
    assert v["month_label"] == "Jul 2026"
    assert v["month_options"] == [
        {"value": "2026-05", "text": "May 2026"},
        {"value": "2026-06", "text": "Jun 2026"},
        {"value": "2026-07", "text": "Jul 2026"},
    ]


def test_month_weeks_lists_each_week_in_selected_month(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-06")
    assert [w["week_label"] for w in v["month_weeks"]] == [
        "2026-W23", "2026-W24", "2026-W27",
    ]
    assert [w["credits"] for w in v["month_weeks"]] == approx([20.0, 30.0, 45.0])
    w27 = v["month_weeks"][-1]
    assert w27["range"] == "29 Jun – 5 Jul"
    weekly = 70 * 100 / 4.33
    assert w27["pct"] == approx(45.0 / weekly)
    assert w27["remaining"] == approx(weekly - 45.0)


def test_month_weekly_chart_labels_and_credits(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-06")
    assert v["month_weekly_chart"]["labels"] == [
        "2026-W23 (1–7 Jun)",
        "2026-W24 (8–14 Jun)",
        "2026-W27 (29 Jun – 5 Jul)",
    ]
    assert v["month_weekly_chart"]["credits"] == approx([20.0, 30.0, 45.0])


def test_month_cumulative_covers_the_months_weeks(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-06")
    mc = v["month_cumulative"]
    assert mc["chart"]["labels"] == [
        "2026-06-01", "2026-06-08", "2026-06-29", "2026-07-01",
    ]
    assert mc["chart"]["cumulative"] == approx([20.0, 50.0, 90.0, 95.0])
    assert mc["total_credits"] == approx(95.0)


def test_unknown_month_falls_back_to_latest(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "1999-01")
    assert v["month"] == "2026-07"


def test_user_view_drops_single_week_daily_breakdown(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-06")
    assert "daily" not in v
    assert "daily_chart" not in v
