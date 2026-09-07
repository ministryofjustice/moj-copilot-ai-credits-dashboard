from pytest import approx

from app.main.services import ai_credits as ac


def test_monthly_view_no_data(fake_source):
    v = ac.monthly_view(fake_source([]), plan=None, month=None)
    assert v["has_data"] is False
    assert not v["months"]


def test_monthly_view_rows_shape_and_top_user(fake_source, month_records):
    v = ac.monthly_view(fake_source(month_records), plan="$200 / month",
                        month="2026-06")
    assert v["has_data"] is True
    assert v["month"] == "2026-06"
    assert "2026-07" in v["months"] and "2026-06" in v["months"]
    top = v["rows"][0]
    assert top["user"] == "a"
    assert top["credits"] == approx(26000.0)
    assert all("top_model" not in r for r in v["rows"])
    assert {"credits", "pct", "remaining", "day_count"} <= v["rows"][0].keys()


def test_monthly_view_uses_full_monthly_allowance(fake_source, month_records):
    # $200 -> 200 * 100 = 20000 credits/month. 'a' spent 26000 -> over 100%.
    v = ac.monthly_view(fake_source(month_records), plan="$200 / month",
                        month="2026-06")
    assert v["allowance"] == approx(20000.0)
    top = v["rows"][0]
    assert top["pct"] == approx(26000.0 / 20000.0)
    assert top["remaining"] == approx(20000.0 - 26000.0)
    assert v["over"] >= 1


def test_monthly_view_selects_requested_month(fake_source, month_records):
    v = ac.monthly_view(fake_source(month_records), plan="$200 / month",
                        month="2026-07")
    assert v["month"] == "2026-07"
    assert {r["user"] for r in v["rows"]} == {"d"}


def test_monthly_view_month_ranges_are_display_labels(fake_source, month_records):
    v = ac.monthly_view(fake_source(month_records), plan="$200 / month",
                        month="2026-06")
    assert v["month_ranges"]["2026-06"] == "Jun 2026"
    assert v["span"] == "Jun 2026"
