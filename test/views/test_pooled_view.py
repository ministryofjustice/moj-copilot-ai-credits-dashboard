from pytest import approx

from app.main.services import ai_credits as ac
from app.main.services.reports_source import ReportsSource


class FakeSource(ReportsSource):
    def __init__(self, records):
        self._records = records

    def daily_docs(self):
        return {}

    def per_user_docs(self, day):
        return {}

    def weekly_records(self):
        return self._records


def _rec(day, user, credits):
    return {"day": day, "user": user, "credits": credits, "usd": credits / 100.0,
            "per_model": {"gpt": credits}}


def test_resolve_seats_defaults_and_validates():
    assert ac.resolve_seats("10") == 10
    assert ac.resolve_seats(None) == 405
    assert ac.resolve_seats("abc") == 405
    assert ac.resolve_seats("-5") == 405
    assert ac.resolve_seats("0") == 405


def _week_records():
    # ISO week 2026-W23 (Mon 2026-06-01 .. Sun 06-07), all in month 2026-06.
    return [
        _rec("2026-06-01", "a", 2000.0),
        _rec("2026-06-02", "b", 50.0),
        _rec("2026-06-03", "c", 30.0),
        _rec("2026-06-04", "d", 20.0),
    ]


def test_pooled_view_no_data():
    v = ac.pooled_view(FakeSource([]), period="weekly", key=None, plan=None, seats=None)
    assert v["has_data"] is False
    assert v["periods"] == []


def test_pooled_view_weekly_overage_maths():
    v = ac.pooled_view(
        FakeSource(_week_records()), period="weekly", key="2026-W23",
        plan="$70 / month", seats="1",
    )
    assert v["has_data"] is True
    assert v["key"] == "2026-W23"
    # weekly allowance = 70 * 100 / 4.33 per seat; pool = seats * allowance
    assert v["allowance"] == approx(70 * 100 / 4.33)
    assert v["metrics"]["pool"] == approx(70 * 100 / 4.33)
    assert v["metrics"]["gross"] == approx(2100.0)
    assert v["metrics"]["overage"] > 0
    assert v["metrics"]["total"] == approx(2100.0)
    # Last tile is the overage tile; tile amounts sum to the total bill.
    assert v["tiles"][-1]["name"] == "Overage"
    assert sum(t["amount"] for t in v["tiles"]) == approx(2100.0, rel=1e-3)


def test_pooled_view_weekly_headroom_tile():
    v = ac.pooled_view(
        FakeSource(_week_records()), period="weekly", key="2026-W23",
        plan="$70 / month", seats="405",
    )
    assert v["metrics"]["headroom"] > 0
    assert v["tiles"][-1]["name"] == "Unused pool"
    # Tiles sum to the pool (= total when within budget).
    assert sum(t["amount"] for t in v["tiles"]) == approx(v["metrics"]["pool"], rel=1e-3)


def test_pooled_view_monthly_allowance():
    v = ac.pooled_view(
        FakeSource(_week_records()), period="monthly", key="2026-06",
        plan="$70 / month", seats="1",
    )
    assert v["period"] == "monthly"
    assert v["key"] == "2026-06"
    assert v["allowance"] == approx(70 * 100)  # monthly = plan$ * 100


def test_pooled_view_seats_override_invalid_falls_back():
    v = ac.pooled_view(
        FakeSource(_week_records()), period="weekly", key="2026-W23",
        plan=None, seats="not-a-number",
    )
    assert v["seats"] == 405
