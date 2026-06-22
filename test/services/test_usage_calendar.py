import app.main.services.ai_credits as ac

# pylint: disable=protected-access


def _recs(pairs):
    return [{"day": d, "credits": c, "usd": c / 100} for d, c in pairs]


def test_window_has_n_weeks_of_seven_days():
    cal = ac._usage_calendar(_recs([("2026-06-10", 1.0)]), daily_allowance=10.0, weeks=9)
    assert len(cal["weeks"]) == 9
    assert all(len(col) == 7 for col in cal["weeks"])  # 63 cells


def test_rightmost_column_contains_latest_day():
    cal = ac._usage_calendar(_recs([("2026-06-16", 5.0)]), daily_allowance=10.0, weeks=9)
    last_col_days = [c["day"] for c in cal["weeks"][-1] if c]
    assert "2026-06-16" in last_col_days


def test_levels_bucket_by_pct_of_daily_allowance():
    recs = _recs([
        ("2026-06-08", 0.0),   # L0
        ("2026-06-09", 1.0),   # 10% -> L1
        ("2026-06-10", 3.0),   # 30% -> L2
        ("2026-06-11", 7.0),   # 70% -> L3
        ("2026-06-12", 12.0),  # 120% -> L4
    ])
    cal = ac._usage_calendar(recs, daily_allowance=10.0, weeks=9)
    by_day = {c["day"]: c["level"] for col in cal["weeks"] for c in col if c}
    assert by_day["2026-06-08"] == 0
    assert by_day["2026-06-09"] == 1
    assert by_day["2026-06-10"] == 2
    assert by_day["2026-06-11"] == 3
    assert by_day["2026-06-12"] == 4


def test_boundaries_are_inclusive_lower():
    recs = _recs([("2026-06-09", 2.5), ("2026-06-10", 5.0), ("2026-06-11", 10.0)])
    cal = ac._usage_calendar(recs, daily_allowance=10.0, weeks=9)
    by_day = {c["day"]: c["level"] for col in cal["weeks"] for c in col if c}
    assert by_day["2026-06-09"] == 2   # exactly 25%
    assert by_day["2026-06-10"] == 3   # exactly 50%
    assert by_day["2026-06-11"] == 4   # exactly 100%


def test_over_budget_days_split_into_graduated_red_tiers():
    recs = _recs([
        ("2026-06-09", 11.0),  # 110% -> L4 (100–150%)
        ("2026-06-10", 20.0),  # 200% -> L5 (150–300%)
        ("2026-06-11", 60.0),  # 600% -> L6 (≥300%)
    ])
    cal = ac._usage_calendar(recs, daily_allowance=10.0, weeks=9)
    by_day = {c["day"]: c["level"] for col in cal["weeks"] for c in col if c}
    assert by_day["2026-06-09"] == 4
    assert by_day["2026-06-10"] == 5
    assert by_day["2026-06-11"] == 6
    colours = {lvl["level"]: lvl["colour"] for lvl in cal["levels"]}
    assert len({colours[4], colours[5], colours[6]}) == 3  # distinct reds


def test_days_without_records_are_level_zero():
    cal = ac._usage_calendar(_recs([("2026-06-16", 5.0)]), daily_allowance=10.0, weeks=9)
    cells = [c for col in cal["weeks"] for c in col if c]
    zeros = [c for c in cells if c["level"] == 0]
    assert len(zeros) >= 1
    assert all(c["credits"] == 0.0 for c in zeros)


def test_cells_are_mapped_to_correct_weekday_row():
    # 2026-06-16 is a Tuesday (ISO weekday 2) -> row index 1
    cal = ac._usage_calendar(_recs([("2026-06-16", 5.0)]), daily_allowance=10.0, weeks=9)
    col = cal["weeks"][-1]
    assert col[1] is not None and col[1]["day"] == "2026-06-16"


def test_empty_records_returns_empty_grid():
    cal = ac._usage_calendar([], daily_allowance=10.0, weeks=9)
    assert not cal["weeks"]
    assert cal["max_credits"] == 0.0
