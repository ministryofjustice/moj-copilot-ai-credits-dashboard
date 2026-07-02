from pytest import approx

from app.main.services import ai_credits as ac


def _urows():
    return [{"day": "2026-06-02", "user_login": "a", "credits": 30.0},
            {"day": "2026-06-02", "user_login": "b", "credits": 10.0}]


def test_daily_view_no_data(fake_source):
    v = ac.daily_view(fake_source([], model_rows=[]))
    assert v["has_data"] is False


def test_daily_view_metrics_and_rollup(fake_source, mrows):
    src = fake_source(_urows(), model_rows=mrows)
    v = ac.daily_view(src, "2026-06-02")
    assert v["day"] == "2026-06-02"
    assert v["scope"] == "ministryofjustice"
    assert v["metrics"]["credits"] == approx(40.0)
    assert v["metrics"]["usd"] == approx(0.4)
    assert v["metrics"]["spenders"] == 2
    assert v["metrics"]["models"] == 1
    assert v["rollup"]["last_day"] == approx(40.0)
    # 06-01 total (80+20) + 06-02 total (40), same ISO week / month.
    assert v["rollup"]["wtd"] == approx(140.0)
    assert v["rollup"]["mtd"] == approx(140.0)


def test_daily_view_family_and_routed_split(fake_source, mrows):
    src = fake_source(_urows(), model_rows=mrows)
    v = ac.daily_view(src, "2026-06-01")
    assert v["family_chart"]["labels"] == ["Opus", "Haiku"]
    assert v["family_chart"]["credits"] == [80.0, 20.0]
    assert v["routed_chart"]["labels"] == ["Auto-routed", "Explicitly chosen"]
    assert v["routed_chart"]["credits"] == [20.0, 80.0]


def test_daily_view_per_user_shares_and_no_dead_fields(fake_source, mrows):
    src = fake_source(_urows(), model_rows=mrows)
    v = ac.daily_view(src, "2026-06-02")
    rows = v["per_user"]["rows"]
    assert rows[0]["user"] == "a" and rows[0]["credits"] == approx(30.0)
    assert rows[0]["share"] == approx(0.75)
    assert all("net" not in r and "top_model" not in r for r in rows)
    assert "fully_covered" not in v and "net" not in v["metrics"]


def test_daily_view_trend_totals_only(fake_source, mrows):
    src = fake_source(_urows(), model_rows=mrows)
    v = ac.daily_view(src, "2026-06-02")
    assert v["trend"]["labels"] == ["2026-06-01", "2026-06-02"]
    assert v["trend"]["totals"] == [100.0, 40.0]
    assert v["trend"]["cumulative"] == [100.0, 140.0]
    assert "net" not in v["trend"]


def _mrow(day, credits):
    return {"day": day, "model": "Opus 4.6", "model_family": "Opus",
            "routed": False, "credits": credits}


def test_daily_view_trend_scoped_to_selected_month(fake_source):
    """Trend includes every day of the selected day's month (full-month shape),
    excluding other months - and never truncates at the selection."""
    src = fake_source([], model_rows=[
        _mrow("2026-06-30", 500.0), _mrow("2026-07-01", 100.0),
        _mrow("2026-07-02", 200.0),
    ])
    # Selecting the earlier July day still shows the whole month, not just up to it.
    v = ac.daily_view(src, "2026-07-01")
    assert v["trend"]["labels"] == ["2026-07-01", "2026-07-02"]
    assert v["trend"]["totals"] == [100.0, 200.0]
    # Cumulative resets at the month boundary - June's 500 is excluded.
    assert v["trend"]["cumulative"] == [100.0, 300.0]


def test_daily_view_trend_highlights_selected_day(fake_source):
    """The selected day's index is flagged so the chart can mark it."""
    src = fake_source([], model_rows=[
        _mrow("2026-07-01", 100.0), _mrow("2026-07-02", 200.0),
    ])
    assert ac.daily_view(src, "2026-07-01")["trend"]["highlight"] == 0
    assert ac.daily_view(src, "2026-07-02")["trend"]["highlight"] == 1


def test_daily_view_trend_none_when_month_has_single_day(fake_source):
    """The reported case: plenty of June data but only one July day, so a July
    selection yields no trend (chart needs 2+ in-month days)."""
    src = fake_source([], model_rows=[
        _mrow("2026-06-29", 400.0), _mrow("2026-06-30", 500.0),
        _mrow("2026-07-01", 100.0),
    ])
    assert ac.daily_view(src, "2026-07-01")["trend"] is None
