from pytest import approx

from app.main.services import ai_credits as ac


def test_weekly_view_no_data(fake_source):
    v = ac.weekly_view(fake_source([]), plan=None, week=None)
    assert v["has_data"] is False
    assert v["weeks"] == []


def test_weekly_view_rows_have_no_top_model(fake_source, week_records):
    v = ac.weekly_view(fake_source(week_records), plan="$70 / month", week="2026-W23")
    assert v["has_data"] is True
    assert v["week"] == "2026-W23"
    top = max(v["rows"], key=lambda r: r["credits"])
    assert top["user"] == "a"
    assert top["credits"] == approx(2000.0)
    # No per-user-per-model data exists -> no top_model column anywhere.
    assert all("top_model" not in r for r in v["rows"])
    assert "credits" in v["rows"][0] and "pct" in v["rows"][0]
    assert "remaining" in v["rows"][0] and "day_count" in v["rows"][0]


def test_weekly_view_counts_over_allowance(fake_source, week_records):
    # 'a' spends 2000 in W23; weekly allowance for $39/mo = 39*100/4.33 ~= 900.
    v = ac.weekly_view(fake_source(week_records), plan="$39 / month", week="2026-W23")
    assert v["over"] >= 1
