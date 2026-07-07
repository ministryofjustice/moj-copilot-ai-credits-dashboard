from pytest import approx

from app.main.services import ai_credits as ac


def test_resolve_seats_defaults_and_validates():
    assert ac.resolve_seats("10") == 10
    assert ac.resolve_seats(None) == 480
    assert ac.resolve_seats("abc") == 480
    assert ac.resolve_seats("-5") == 480
    assert ac.resolve_seats("0") == 480


def test_pooled_view_no_data(fake_source):
    v = ac.pooled_view(fake_source([]), period="weekly", key=None, plan=None, seats=None)
    assert v["has_data"] is False
    assert v["periods"] == []


def test_pooled_view_weekly_overage_maths(fake_source, week_records):
    v = ac.pooled_view(
        fake_source(week_records), period="weekly", key="2026-W23",
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


def test_pooled_view_weekly_headroom_tile(fake_source, week_records):
    v = ac.pooled_view(
        fake_source(week_records), period="weekly", key="2026-W23",
        plan="$70 / month", seats="405",
    )
    assert v["metrics"]["headroom"] > 0
    assert v["tiles"][-1]["name"] == "Unused pool"
    # Tiles sum to the pool (= total when within budget).
    assert sum(t["amount"] for t in v["tiles"]) == approx(v["metrics"]["pool"], rel=1e-3)


def test_pooled_view_monthly_allowance(fake_source, week_records):
    v = ac.pooled_view(
        fake_source(week_records), period="monthly", key="2026-06",
        plan="$70 / month", seats="1",
    )
    assert v["period"] == "monthly"
    assert v["key"] == "2026-06"
    assert v["allowance"] == approx(70 * 100)  # monthly = plan$ * 100


def test_pooled_view_seats_override_invalid_falls_back(fake_source, week_records):
    v = ac.pooled_view(
        fake_source(week_records), period="weekly", key="2026-W23",
        plan=None, seats="not-a-number",
    )
    assert v["seats"] == 480


def _month_recs(month, days, user="u1", amount=100.0):
    """Per-user source rows for days 1..N of `month`, flat daily `amount`."""
    return [{"day": f"{month}-{d:02d}", "user_login": user, "credits": amount}
            for d in range(1, days + 1)]


# ---- cumulative usage + month-end projection (pooled page) -------------------

def test_pooled_cumulative_none_in_weekly_mode(fake_source, week_records):
    v = ac.pooled_view(fake_source(week_records), period="weekly", key="2026-W23",
                       plan="$70 / month", seats="1")
    assert v["cumulative"] is None


def test_pooled_cumulative_reconciles_to_gross(fake_source, week_records):
    v = ac.pooled_view(fake_source(week_records), period="monthly", key="2026-06",
                       plan="$70 / month", seats="1")
    cum = v["cumulative"]
    assert cum is not None
    assert cum["month"] == "2026-06"
    last = next(x for x in reversed(cum["current"]) if x is not None)
    assert last == round(v["metrics"]["gross"], 1)
    assert len(cum["labels"]) == 30  # June
    assert len(cum["current"]) == 30
    assert cum["pool"] == v["metrics"]["pool"]


def test_pooled_projection_hidden_before_five_days(fake_source):
    recs = _month_recs("2026-07", 4)  # only 4 elapsed days
    v = ac.pooled_view(fake_source(recs), period="monthly", key="2026-07",
                       plan="$70 / month", seats="1")
    assert v["cumulative"]["pace"] is None
    assert v["cumulative"]["projection"] is None


def test_pooled_projection_present_and_linear_at_five_days(fake_source):
    recs = _month_recs("2026-07", 5, amount=100.0)  # mtd=500 over 5 days
    v = ac.pooled_view(fake_source(recs), period="monthly", key="2026-07",
                       plan="$70 / month", seats="1")
    cum = v["cumulative"]
    assert cum["pace"] is not None
    # 31-day July, rate = 500/5 = 100/day -> projected 3100 at day 31
    assert cum["pace"]["projected"] == approx(3100.0)
    proj = cum["projection"]
    assert len(proj) == 31
    assert proj[:4] == [None, None, None, None]  # null before day 5
    assert proj[4] == approx(500.0)              # meets current line at day 5
    assert proj[30] == approx(3100.0)            # month-end projection


def test_pooled_projection_none_on_completed_month(fake_source):
    # July is the latest month in data, so June is complete -> no projection
    recs = _month_recs("2026-06", 30) + _month_recs("2026-07", 3)
    v = ac.pooled_view(fake_source(recs), period="monthly", key="2026-06",
                       plan="$70 / month", seats="1")
    assert v["cumulative"]["pace"] is None
    assert v["cumulative"]["projection"] is None
    assert all(x is not None for x in v["cumulative"]["current"])


def test_pooled_prior_none_without_prior_data(fake_source):
    recs = _month_recs("2026-07", 5)  # no June data
    v = ac.pooled_view(fake_source(recs), period="monthly", key="2026-07",
                       plan="$70 / month", seats="1")
    assert v["cumulative"]["prior"] is None


def test_pooled_prior_overlay_aligned_by_day_of_month(fake_source):
    recs = _month_recs("2026-06", 30, amount=100.0) + _month_recs("2026-07", 5)
    v = ac.pooled_view(fake_source(recs), period="monthly", key="2026-07",
                       plan="$70 / month", seats="1")
    prior = v["cumulative"]["prior"]
    assert prior["month"] == "2026-06"
    assert prior["month_label"] == "Jun 2026"
    # aligned to July width (31): June day-15 cumulative sits at index 14
    assert len(prior["cumulative"]) == 31
    assert prior["cumulative"][14] == approx(1500.0)  # 15 days * 100
    assert prior["cumulative"][29] == approx(3000.0)  # June day 30
    assert prior["cumulative"][30] is None            # no June day 31
