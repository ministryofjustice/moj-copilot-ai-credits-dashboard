from pytest import approx

from app.main.services import ai_credits as ac


def _mrows():
    return [
        {"day": "2026-06-01", "model": "Opus 4.6", "model_family": "Opus",
         "routed": False, "credits": 80.0},
        {"day": "2026-06-01", "model": "Auto: Haiku", "model_family": "Haiku",
         "routed": True, "credits": 20.0},
        {"day": "2026-06-02", "model": "Opus 4.6", "model_family": "Opus",
         "routed": False, "credits": 40.0},
    ]


def _urows():
    return [{"day": "2026-06-02", "user_login": "a", "credits": 30.0},
            {"day": "2026-06-02", "user_login": "b", "credits": 10.0}]


def test_daily_view_no_data(fake_source):
    v = ac.daily_view(fake_source([], model_rows=[]))
    assert v["has_data"] is False


def test_daily_view_metrics_and_rollup(fake_source):
    src = fake_source(_urows(), model_rows=_mrows())
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


def test_daily_view_family_and_routed_split(fake_source):
    src = fake_source(_urows(), model_rows=_mrows())
    v = ac.daily_view(src, "2026-06-01")
    assert v["family_chart"]["labels"] == ["Opus", "Haiku"]
    assert v["family_chart"]["credits"] == [80.0, 20.0]
    assert v["routed_chart"]["labels"] == ["Auto-routed", "Explicitly chosen"]
    assert v["routed_chart"]["credits"] == [20.0, 80.0]


def test_daily_view_per_user_shares_and_no_dead_fields(fake_source):
    src = fake_source(_urows(), model_rows=_mrows())
    v = ac.daily_view(src, "2026-06-02")
    rows = v["per_user"]["rows"]
    assert rows[0]["user"] == "a" and rows[0]["credits"] == approx(30.0)
    assert rows[0]["share"] == approx(0.75)
    assert all("net" not in r and "top_model" not in r for r in rows)
    assert "fully_covered" not in v and "net" not in v["metrics"]


def test_daily_view_trend_totals_only(fake_source):
    src = fake_source(_urows(), model_rows=_mrows())
    v = ac.daily_view(src, "2026-06-02")
    assert v["trend"]["labels"] == ["2026-06-01", "2026-06-02"]
    assert v["trend"]["totals"] == [100.0, 40.0]
    assert v["trend"]["cumulative"] == [100.0, 140.0]
    assert "net" not in v["trend"]
