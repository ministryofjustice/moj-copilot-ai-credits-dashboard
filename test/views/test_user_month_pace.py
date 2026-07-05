"""Tests for the My-usage projected-pace panel (`month_pace`).

For a month still in progress (the latest captured day, org-wide, falls inside
it before month end) the view projects the user's month-to-date credits to a
full-month figure at the current daily pace and compares it against the
monthly allowance. Completed months carry no pace data (`month_pace is None`).
"""

from pytest import approx

from app.main.services import ai_credits as ac

MONTHLY_70 = 70 * 100.0  # $70 plan = 7000 credits / month


def _rows(make_record):
    return [
        make_record("2026-06-01", "alice", 20.0),
        make_record("2026-06-29", "alice", 40.0),
        make_record("2026-07-01", "alice", 5.0),
        make_record("2026-07-06", "alice", 7.0),
    ]


def test_pace_projects_mtd_to_full_month(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-07")
    pace = v["month_pace"]
    assert pace is not None
    # 12 credits over 6 elapsed days of a 31-day July.
    assert pace["days_elapsed"] == 6
    assert pace["days_in_month"] == 31
    assert pace["projected"] == approx(12.0 / 6 * 31, abs=0.05)
    assert pace["pct"] == approx(pace["projected"] / MONTHLY_70, rel=1e-3)
    assert pace["delta"] == approx(pace["projected"] - MONTHLY_70, abs=0.05)
    assert pace["status"] == "under"


def test_no_pace_before_five_days_of_data(fake_source, make_record):
    """Fewer than 5 elapsed days is too noisy to project a whole month from."""
    rows = [make_record("2026-07-01", "alice", 5.0),
            make_record("2026-07-04", "alice", 7.0)]
    v = ac.user_view(fake_source(rows), "alice", "$70 / month", "2026-07")
    assert v["month_pace"] is None


def test_pace_appears_from_the_fifth_day(fake_source, make_record):
    rows = [make_record("2026-07-01", "alice", 5.0),
            make_record("2026-07-05", "alice", 7.0)]
    v = ac.user_view(fake_source(rows), "alice", "$70 / month", "2026-07")
    assert v["month_pace"] is not None
    assert v["month_pace"]["days_elapsed"] == 5


def test_no_pace_for_completed_month(fake_source, make_record):
    v = ac.user_view(fake_source(_rows(make_record)), "alice", "$70 / month", "2026-06")
    assert v["month_pace"] is None


def test_days_elapsed_anchored_to_org_latest_day(fake_source, make_record):
    """An idle user's pace must not stall: elapsed days come from the latest
    day captured across the whole org, not the user's own latest record."""
    rows = _rows(make_record) + [make_record("2026-07-10", "bob", 1.0)]
    v = ac.user_view(fake_source(rows), "alice", "$70 / month", "2026-07")
    pace = v["month_pace"]
    assert pace["days_elapsed"] == 10
    assert pace["projected"] == approx(12.0 / 10 * 31, abs=0.05)


def test_pace_status_over_when_projection_exceeds_allowance(fake_source, make_record):
    rows = [make_record("2026-07-01", "alice", 3000.0),
            make_record("2026-07-06", "alice", 3000.0)]
    v = ac.user_view(fake_source(rows), "alice", "$70 / month", "2026-07")
    pace = v["month_pace"]
    assert pace["projected"] == approx(6000.0 / 6 * 31, abs=0.5)  # 31000 >> 7000
    assert pace["status"] == "over"
    assert pace["delta"] > 0


def test_pace_status_on_track_near_allowance(fake_source, make_record):
    # 1354.8 credits over 6 of 31 days projects to ~7000 (within ±2%).
    rows = [make_record("2026-07-06", "alice", 1354.8)]
    v = ac.user_view(fake_source(rows), "alice", "$70 / month", "2026-07")
    assert v["month_pace"]["status"] == "on-track"


def test_no_pace_when_latest_day_is_month_end(fake_source, make_record):
    rows = [make_record("2026-06-01", "alice", 20.0),
            make_record("2026-06-30", "alice", 10.0)]
    v = ac.user_view(fake_source(rows), "alice", "$70 / month", "2026-06")
    assert v["month_pace"] is None
