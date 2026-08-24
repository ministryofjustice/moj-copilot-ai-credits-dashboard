# pylint: disable=protected-access
from datetime import date

from pytest import approx

from app.main.services import ai_credits as ac
from app.main.services import weekly_per_user as wpu


def test_resolve_seats_defaults_and_validates():
    assert ac.resolve_seats("10") == 10
    assert ac.resolve_seats(None) == 480
    assert ac.resolve_seats("abc") == 480
    assert ac.resolve_seats("-5") == 480
    assert ac.resolve_seats("0") == 480


def test_resolve_seats_enforces_upper_bound():
    assert ac.resolve_seats("2000") == 2000
    assert ac.resolve_seats("2001") == 480
    assert ac.resolve_seats("999999999999999999") == 480


def test_resolve_seats_accepts_only_plain_digit_strings():
    assert ac.resolve_seats("1_000") == 480
    assert ac.resolve_seats(" 12 ") == 480
    assert ac.resolve_seats("+5") == 480
    assert ac.resolve_seats("١٢") == 480  # non-ASCII digits int() would accept
    assert ac.resolve_seats("12.0") == 480
    assert ac.resolve_seats("<script>alert(1)</script>") == 480
    assert ac.resolve_seats("1e3") == 480
    assert ac.resolve_seats("0" * 5000) == 480  # absurdly long digit string


def test_pooled_view_no_data(fake_source):
    v = ac.pooled_view(fake_source([]), period="weekly", key=None, plan=None, seats=None)
    assert v["has_data"] is False
    assert v["periods"] == []


def test_pooled_view_weekly_overage_maths(fake_source, week_records):
    v = ac.pooled_view(
        fake_source(week_records), period="weekly", key="2026-W23",
        plan="$39 / month", seats="1",
    )
    assert v["has_data"] is True
    assert v["key"] == "2026-W23"
    # weekly allowance = 39 * 100 / 4.33 per seat; pool = seats * allowance
    assert v["allowance"] == approx(39 * 100 / 4.33)
    assert v["metrics"]["pool"] == approx(39 * 100 / 4.33)
    assert v["metrics"]["gross"] == approx(2100.0)
    assert v["metrics"]["overage"] > 0
    assert v["metrics"]["total"] == approx(2100.0)
    # Last tile is the overage tile; tile amounts sum to the total bill.
    assert v["tiles"][-1]["name"] == "Overage"
    assert sum(t["amount"] for t in v["tiles"]) == approx(2100.0, rel=1e-3)


def test_pooled_view_weekly_headroom_tile(fake_source, week_records):
    v = ac.pooled_view(
        fake_source(week_records), period="weekly", key="2026-W23",
        plan="$39 / month", seats="405",
    )
    assert v["metrics"]["headroom"] > 0
    assert v["tiles"][-1]["name"] == "Unused pool"
    # Tiles sum to the pool (= total when within budget).
    assert sum(t["amount"] for t in v["tiles"]) == approx(v["metrics"]["pool"], rel=1e-3)


def test_pooled_view_monthly_allowance(fake_source, week_records):
    v = ac.pooled_view(
        fake_source(week_records), period="monthly", key="2026-06",
        plan="$39 / month", seats="1",
    )
    assert v["period"] == "monthly"
    assert v["key"] == "2026-06"
    assert v["allowance"] == approx(39 * 100)  # monthly = plan$ * 100


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
                       plan="$39 / month", seats="1")
    assert v["cumulative"] is None


def test_pooled_cumulative_reconciles_to_gross(fake_source, week_records):
    v = ac.pooled_view(fake_source(week_records), period="monthly", key="2026-06",
                       plan="$39 / month", seats="1")
    cum = v["cumulative"]
    assert cum is not None
    assert cum["month"] == "2026-06"
    last = next(x for x in reversed(cum["current"]) if x is not None)
    assert last == round(v["metrics"]["gross"], 1)
    assert len(cum["labels"]) == 30  # June
    assert len(cum["current"]) == 30
    assert cum["pool"] == v["metrics"]["pool"]


def test_pooled_cumulative_tooltip_labels_are_full_dates(fake_source, week_records):
    """Axis labels stay compact; the tooltip gets the unambiguous full date."""
    v = ac.pooled_view(fake_source(week_records), period="monthly", key="2026-06",
                       plan="$39 / month", seats="1")
    cum = v["cumulative"]
    assert cum["tooltip_labels"][0] == "Mon 01 Jun 2026"
    assert cum["tooltip_labels"][29] == "Tue 30 Jun 2026"
    assert len(cum["tooltip_labels"]) == len(cum["labels"])


def test_pooled_projection_hidden_before_five_days(fake_source):
    recs = _month_recs("2026-07", 4)  # only 4 elapsed days
    v = ac.pooled_view(fake_source(recs), period="monthly", key="2026-07",
                       plan="$39 / month", seats="1")
    assert v["cumulative"]["pace"] is None
    assert v["cumulative"]["projection"] is None


def test_pooled_projection_present_and_linear_at_five_days(fake_source):
    recs = _month_recs("2026-07", 5, amount=100.0)  # mtd=500 over 5 days
    v = ac.pooled_view(fake_source(recs), period="monthly", key="2026-07",
                       plan="$39 / month", seats="1")
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
                       plan="$39 / month", seats="1")
    assert v["cumulative"]["pace"] is None
    assert v["cumulative"]["projection"] is None
    assert all(x is not None for x in v["cumulative"]["current"])


def test_pooled_prior_none_without_prior_data(fake_source):
    recs = _month_recs("2026-07", 5)  # no June data
    v = ac.pooled_view(fake_source(recs), period="monthly", key="2026-07",
                       plan="$39 / month", seats="1")
    assert v["cumulative"]["prior"] is None


def test_pooled_prior_overlay_aligned_by_day_of_month(fake_source):
    recs = _month_recs("2026-06", 30, amount=100.0) + _month_recs("2026-07", 5)
    v = ac.pooled_view(fake_source(recs), period="monthly", key="2026-07",
                       plan="$39 / month", seats="1")
    prior = v["cumulative"]["prior"]
    assert prior["month"] == "2026-06"
    assert prior["month_label"] == "Jun 2026"
    # aligned to July width (31): June day-15 cumulative sits at index 14
    assert len(prior["cumulative"]) == 31
    assert prior["cumulative"][14] == approx(1500.0)  # 15 days * 100
    assert prior["cumulative"][29] == approx(3000.0)  # June day 30
    assert prior["cumulative"][30] is None            # no June day 31


# ---------------------------------------------------------------------------
# _routed_trend tests
# ---------------------------------------------------------------------------

def _mr(day, routed, amount, model="M", fam="F"):
    """One org per-model row for the routed-trend tests."""
    return {"day": day, "model": model, "model_family": fam,
            "routed": routed, "credits": amount}


def _trend_rows():
    """Two captured June days: day 1 has both routed+chosen, day 2 both too."""
    return [
        _mr("2026-06-01", True, 20.0), _mr("2026-06-01", False, 80.0),
        _mr("2026-06-02", False, 40.0), _mr("2026-06-02", True, 10.0),
    ]


def test_routed_trend_monthly_sums_and_mtd_heading():
    t = ac._routed_trend(_trend_rows(), "monthly", "2026-06",
                         latest_day="2026-06-02")
    assert t["labels"] == [str(d) for d in range(1, 31)]  # June has 30 days
    assert t["routed"] == [20.0, 10.0] + [None] * 28
    assert t["chosen"] == [80.0, 40.0] + [None] * 28
    # names the month as the cumulative chart does, plus the in-progress note
    assert t["heading"] == "Jun 2026 (month to date)"


def test_routed_trend_past_month_uses_plain_label():
    rows = _trend_rows() + [_mr("2026-07-01", False, 5.0)]
    t = ac._routed_trend(rows, "monthly", "2026-06", latest_day="2026-07-01")
    assert t["heading"] == "Jun 2026"  # June is complete, not "to date"
    # June is fully in the past: every day is real (0.0 fill), no trailing None
    assert t["labels"] == [str(d) for d in range(1, 31)]
    assert t["routed"] == [20.0, 10.0] + [0.0] * 28  # July row excluded by period filter
    assert t["chosen"] == [80.0, 40.0] + [0.0] * 28


def test_routed_trend_weekly_filters_and_labels():
    key = wpu.iso_week_label("2026-06-01")[0]
    t = ac._routed_trend(_trend_rows(), "weekly", key, latest_day="2026-06-02")
    week_days = ("2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04",
                 "2026-06-05", "2026-06-06", "2026-06-07")
    expected_labels = [date.fromisoformat(d).strftime("%a %d") for d in week_days]
    assert t["labels"] == expected_labels
    assert t["routed"] == [20.0, 10.0, None, None, None, None, None]
    assert t["chosen"] == [80.0, 40.0, None, None, None, None, None]
    week_range = wpu.format_week_range(*(int(p) for p in key.split("-W")))
    assert t["heading"] == f"{key} ({week_range}, week to date)"


def test_routed_trend_tooltip_labels_are_full_dates():
    """Axis labels stay compact; the tooltip gets the unambiguous full date."""
    t = ac._routed_trend(_trend_rows(), "monthly", "2026-06",
                         latest_day="2026-06-02")
    assert t["tooltip_labels"][0] == "Mon 01 Jun 2026"
    assert t["tooltip_labels"][29] == "Tue 30 Jun 2026"
    assert len(t["tooltip_labels"]) == len(t["labels"])


def test_routed_trend_weekly_tooltip_labels_are_full_dates():
    key = wpu.iso_week_label("2026-06-01")[0]
    t = ac._routed_trend(_trend_rows(), "weekly", key, latest_day="2026-06-02")
    assert t["tooltip_labels"][0] == "Mon 01 Jun 2026"
    assert len(t["tooltip_labels"]) == 7


def test_routed_trend_none_when_period_empty():
    assert ac._routed_trend(_trend_rows(), "monthly", "2099-01",
                            latest_day="2026-06-02") is None
    assert ac._routed_trend([], "monthly", "2026-06", latest_day=None) is None


def test_routed_trend_asymmetric_day_zero_fills_other_series():
    rows = [_mr("2026-06-01", True, 15.0),
            _mr("2026-06-02", False, 30.0)]
    t = ac._routed_trend(rows, "monthly", "2026-06", latest_day="2026-06-02")
    assert t["labels"][:2] == ["1", "2"]
    assert t["routed"] == [15.0, 0.0] + [None] * 28
    assert t["chosen"] == [0.0, 30.0] + [None] * 28


def test_routed_trend_weekly_zero_fills_and_truncates_midweek():
    """Data on Mon (day1) and Thu (day4) only; latest_day is Thu.

    Tue/Wed have no usage but have already elapsed, so they must show 0.0 (not
    None); Fri-Sun haven't happened yet, so they must be None so both lines
    stop at Thursday instead of running flat to Sunday.
    """
    key = wpu.iso_week_label("2026-06-01")[0]
    rows = [_mr("2026-06-01", True, 12.0), _mr("2026-06-04", False, 8.0)]
    t = ac._routed_trend(rows, "weekly", key, latest_day="2026-06-04")
    assert t["routed"] == [12.0, 0.0, 0.0, 0.0, None, None, None]
    assert t["chosen"] == [0.0, 0.0, 0.0, 8.0, None, None, None]


# ---------------------------------------------------------------------------
# pooled_view routed_trend integration tests
# ---------------------------------------------------------------------------

def test_pooled_view_surfaces_routed_trend(fake_source, week_records):
    src = fake_source(week_records, model_rows=_trend_rows())
    v = ac.pooled_view(src, period="monthly", key="2026-06",
                       plan="$39 / month", seats="1")
    rt = v["routed_trend"]
    assert rt is not None
    assert rt["labels"] == [str(d) for d in range(1, 31)]
    assert rt["routed"] == [20.0, 10.0] + [None] * 28
    assert rt["chosen"] == [80.0, 40.0] + [None] * 28
    assert rt["heading"] == "Jun 2026 (month to date)"


def test_pooled_view_routed_trend_none_without_model_rows(fake_source,
                                                          week_records):
    v = ac.pooled_view(fake_source(week_records), period="monthly",
                       key="2026-06", plan="$39 / month", seats="1")
    assert v["routed_trend"] is None


def test_pooled_view_routed_trend_heading_uses_model_latest_day(fake_source):
    # User rows end in June, so the monthly block sets latest_day="2026-06-01"
    # from user records. Model rows extend into July, so model_latest_day should
    # be "2026-07-01". The June trend heading must be the plain "Jun 2026" label
    # (June is complete from the model-data perspective), not "month to date".
    user_rows = [
        {"day": "2026-06-01", "user_login": "a", "credits": 100.0},
    ]
    model_rows = [
        {"day": "2026-06-01", "model": "M", "model_family": "F",
         "routed": True, "credits": 20.0},
        {"day": "2026-06-01", "model": "M", "model_family": "F",
         "routed": False, "credits": 80.0},
        {"day": "2026-07-01", "model": "M", "model_family": "F",
         "routed": True, "credits": 5.0},
    ]
    v = ac.pooled_view(fake_source(user_rows, model_rows=model_rows),
                       period="monthly", key="2026-06",
                       plan="$39 / month", seats="1")
    assert v["routed_trend"]["heading"] == "Jun 2026"
