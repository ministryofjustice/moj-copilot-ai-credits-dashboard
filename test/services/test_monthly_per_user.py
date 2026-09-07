from pytest import approx

import app.main.services.weekly_per_user as wpu


def test_rollup_monthly_empty_input_returns_empty_list():
    assert wpu.rollup_monthly([]) == []


def test_rollup_monthly_sums_credits_per_month_and_user():
    records = [
        {"day": "2026-06-01", "user": "a", "credits": 2000.0},
        {"day": "2026-06-30", "user": "a", "credits": 500.0},
        {"day": "2026-07-01", "user": "a", "credits": 10.0},
        {"day": "2026-06-15", "user": "b", "credits": 40.0},
    ]
    rows = wpu.rollup_monthly(records)
    by_key = {(r["month_label"], r["user"]): r for r in rows}
    assert by_key[("2026-06", "a")]["credits"] == approx(2500.0)
    assert by_key[("2026-06", "a")]["day_count"] == 2
    assert by_key[("2026-07", "a")]["credits"] == approx(10.0)
    assert by_key[("2026-06", "b")]["credits"] == approx(40.0)


def test_rollup_monthly_counts_distinct_days_only():
    records = [
        {"day": "2026-06-01", "user": "a", "credits": 5.0},
        {"day": "2026-06-01", "user": "a", "credits": 7.0},
        {"day": "2026-06-02", "user": "a", "credits": 3.0},
    ]
    rows = wpu.rollup_monthly(records)
    assert len(rows) == 1
    assert rows[0]["credits"] == approx(15.0)
    assert rows[0]["day_count"] == 2


def test_rollup_monthly_sorts_by_month_asc_then_credits_desc():
    records = [
        {"day": "2026-07-01", "user": "x", "credits": 1.0},
        {"day": "2026-06-01", "user": "low", "credits": 10.0},
        {"day": "2026-06-01", "user": "high", "credits": 90.0},
    ]
    rows = wpu.rollup_monthly(records)
    assert [(r["month_label"], r["user"]) for r in rows] == [
        ("2026-06", "high"), ("2026-06", "low"), ("2026-07", "x"),
    ]
