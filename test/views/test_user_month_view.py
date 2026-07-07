"""Tests for the My-usage month selector and its per-week cost stats.

The personal page selects a *calendar month* and shows weekly cost stats for
each ISO week that has usage in that month. Weeks keep their whole-week
credits (the allowance is weekly), so a week that straddles a month boundary
(e.g. 2026-W27, 29 Jun – 5 Jul) appears under both months, but the cumulative
chart and the month list are scoped strictly to calendar days.
"""

from pytest import approx

from app.main.services import ai_credits as ac


def _rows(make_record):
    # alice spans three months; 2026-W27 straddles Jun/Jul (29 Jun – 5 Jul).
    return [
        make_record("2026-05-25", "alice", 10.0),   # 2026-W22, May
        make_record("2026-06-01", "alice", 20.0),   # 2026-W23, Jun
        make_record("2026-06-08", "alice", 30.0),   # 2026-W24, Jun
        make_record("2026-06-29", "alice", 40.0),   # 2026-W27, Jun side
        make_record("2026-07-01", "alice", 5.0),    # 2026-W27, Jul side
        make_record("2026-07-06", "alice", 7.0),    # 2026-W28, Jul
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


def test_month_selectable_before_first_full_iso_week(fake_source, make_record):
    """July must be offered as soon as any July day exists, even while every
    July record still sits in a week whose Monday falls in June (the bug that
    hid July from the menu)."""
    rows = _rows(make_record)[:-1]  # drop 2026-07-06; only 2026-07-01 remains
    v = ac.user_view(fake_source(rows), "alice", "$70 / month")
    assert v["months"] == ["2026-05", "2026-06", "2026-07"]
    assert v["month"] == "2026-07"


def test_month_weeks_lists_each_week_touching_selected_month(fake_source, make_record):
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


def test_straddling_week_appears_under_both_months(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-07")
    assert [w["week_label"] for w in v["month_weeks"]] == ["2026-W27", "2026-W28"]
    # Whole-week credits (the allowance is weekly), not just the July days.
    assert [w["credits"] for w in v["month_weeks"]] == approx([45.0, 7.0])


def test_month_weekly_chart_labels_and_credits(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-06")
    assert v["month_weekly_chart"]["labels"] == [
        "2026-W23 (1–7 Jun)",
        "2026-W24 (8–14 Jun)",
        "2026-W27 (29 Jun – 5 Jul)",
    ]
    assert v["month_weekly_chart"]["credits"] == approx([20.0, 30.0, 45.0])


def test_month_cumulative_scoped_to_calendar_days(fake_source, make_record):
    """June's cumulative chart must contain June days only — no July spill-over
    from the straddling week (the bug that showed July data under Jun 2026)."""
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-06")
    mc = v["month_cumulative"]
    assert mc["chart"]["labels"] == ["2026-06-01", "2026-06-08", "2026-06-29"]
    assert mc["chart"]["cumulative"] == approx([20.0, 50.0, 90.0])
    assert mc["total_credits"] == approx(90.0)


def test_month_cumulative_resets_at_month_start(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-07")
    mc = v["month_cumulative"]
    assert mc["chart"]["labels"] == ["2026-07-01", "2026-07-06"]
    assert mc["chart"]["cumulative"] == approx([5.0, 12.0])
    assert mc["total_credits"] == approx(12.0)


def test_unknown_month_falls_back_to_latest(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "1999-01")
    assert v["month"] == "2026-07"


def test_user_view_drops_single_week_daily_breakdown(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-06")
    assert "daily" not in v
    assert "daily_chart" not in v
