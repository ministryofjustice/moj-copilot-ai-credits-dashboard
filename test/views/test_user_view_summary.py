from pytest import approx

from app.main.services import ai_credits as ac


def _rows():
    # user 'a': two days in ISO week 2026-W26 (Mon 22 / Tue 23 Jun) + one earlier.
    return [
        {"day": "2026-06-22", "user_login": "a", "credits": 100.0},
        {"day": "2026-06-23", "user_login": "a", "credits": 50.0},
        {"day": "2026-06-15", "user_login": "a", "credits": 9.0},
        {"day": "2026-06-23", "user_login": "b", "credits": 7.0},  # other user
    ]


def test_summary_anchors_to_latest_day(fake_source):
    v = ac.user_view(fake_source(_rows()), "a", "$70 / month", None)
    s = v["summary"]
    assert s["as_of"] == "2026-06-23"
    assert s["last_day"]["credits"] == approx(50.0)
    assert s["wtd"]["credits"] == approx(150.0)   # 22nd + 23rd, same ISO week
    assert s["wtd"]["week_label"] == "2026-W26"
    assert s["wtd"]["days"] == 2
    assert s["mtd"]["credits"] == approx(159.0)    # whole of June so far


def test_summary_pct_against_allowances(fake_source):
    v = ac.user_view(fake_source(_rows()), "a", "$70 / month", None)
    s = v["summary"]
    weekly = 70 * 100 / 4.33
    assert s["wtd"]["allowance"] == approx(weekly)
    assert s["wtd"]["pct"] == approx(150.0 / weekly)
    assert s["wtd"]["remaining"] == approx(weekly - 150.0)
    assert s["mtd"]["allowance"] == approx(70 * 100)
    assert s["last_day"]["allowance"] == approx(weekly / 7.0)


def test_example_login_picks_only_from_top_spenders(fake_source):
    # 20 users, descending spend u00 (highest) .. u19 (lowest).
    rows = [{"day": "2026-06-01", "user_login": f"u{i:02d}",
             "credits": float(100 - i)} for i in range(20)]
    src = fake_source(rows)
    picks = {ac.example_login(src) for _ in range(80)}
    assert picks  # never empty when data exists
    assert picks <= {f"u{i:02d}" for i in range(10)}  # only the top 10 eligible


def test_example_login_empty_when_no_data(fake_source):
    assert ac.example_login(fake_source([])) == ""


def test_user_view_drops_top_model(fake_source):
    v = ac.user_view(fake_source(_rows()), "a", "$70 / month", None)
    assert "top_model" not in v
    assert all("top_model" not in w for w in v["weekly"])
    assert all("usd" not in w for w in v["weekly"])
