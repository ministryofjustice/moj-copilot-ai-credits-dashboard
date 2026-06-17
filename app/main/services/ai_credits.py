"""View-model builders for the AI-credits dashboard.

Turns a `ReportsSource` into plain, JSON-serialisable structures the templates
and Chart.js consume. No Flask and no Streamlit here — just data shaping — so it
stays unit-testable and backend-agnostic.

Ported from copilot-daily/ai_credits_app.py (the `load_days` / `load_per_user` /
`load_weekly_rollup` loaders + the per-tab layout maths), minus Streamlit and
minus `@st.cache_data`.
"""

from __future__ import annotations

from app.main.services import weekly_per_user as wpu
from app.main.services.reports_source import ReportsSource

# Per-seat allowance maths. Credits bill at $0.01 each ($1 == 100 credits). The
# included allowance is monthly; spread across an average ISO week (month / 4.33)
# to get the weekly denominator for the "% used / remaining" view.
CREDITS_PER_USD = 100.0
WEEKS_PER_MONTH = 4.33
# Selectable monthly per-seat AI-credit budgets (USD).
PLAN_TIERS_USD_PER_MONTH = {"$70 / month": 70.0, "$39 / month": 39.0}
DEFAULT_PLAN = "$70 / month"


def plan_labels() -> list[str]:
    return list(PLAN_TIERS_USD_PER_MONTH)


def resolve_plan(plan: str | None) -> str:
    return plan if plan in PLAN_TIERS_USD_PER_MONTH else DEFAULT_PLAN


def weekly_allowance(plan: str) -> float:
    """Weekly per-seat credit allowance for a plan label."""
    monthly_usd = PLAN_TIERS_USD_PER_MONTH[resolve_plan(plan)]
    return monthly_usd * CREDITS_PER_USD / WEEKS_PER_MONTH


def plan_limits(plan: str) -> dict:
    """Per-seat credit allowance at each timeframe, derived from the plan.

    Monthly is the headline budget ($1 = 100 credits); weekly spreads it over an
    average ISO week (month / 4.33); daily is the weekly figure / 7.
    """
    plan = resolve_plan(plan)
    weekly = weekly_allowance(plan)
    monthly = PLAN_TIERS_USD_PER_MONTH[plan] * CREDITS_PER_USD
    return {"daily": weekly / 7.0, "weekly": weekly, "monthly": monthly}


# ----------------------------------------------------------------- daily helpers
def _totals(items: list[dict]) -> tuple[float, float, float]:
    gross = sum(i.get("grossAmount", 0.0) for i in items)
    net = sum(i.get("netAmount", 0.0) for i in items)
    total_credits = sum(i.get("grossQuantity", 0.0) for i in items)
    return gross, net, total_credits


def _by_model(items: list[dict]) -> list[dict]:
    """Aggregate usageItems by model, gross-spend descending, spenders only."""
    agg: dict[str, dict] = {}
    for i in items:
        m = agg.setdefault(i["model"], {"model": i["model"], "gross": 0.0, "net": 0.0})
        m["gross"] += i.get("grossAmount", 0.0)
        m["net"] += i.get("netAmount", 0.0)
    rows = [r for r in agg.values() if r["gross"] > 0]
    rows.sort(key=lambda r: r["gross"], reverse=True)
    return rows


def daily_view(source: ReportsSource, day: str | None = None) -> dict:  # pylint: disable=too-many-locals
    """Everything the Daily admin page needs for one day, plus the MTD trend."""
    docs = source.daily_docs()
    if not docs:
        return {"has_data": False, "days": []}

    days = list(docs)
    day = day if day in docs else days[-1]
    doc = docs[day]
    scope = doc.get("organization") or doc.get("enterprise") or "?"
    items = doc.get("usageItems", [])
    gross, net, total_credits = _totals(items)

    by_model = _by_model(items)
    for r in by_model:
        r["share"] = (r["gross"] / gross) if gross else 0.0

    # Month-to-date trend (only meaningful with 2+ days captured).
    trend = None
    if len(days) >= 2:
        labels, g_series, n_series, cumulative = [], [], [], []
        running = 0.0
        for d in days:
            dg, dn, _ = _totals(docs[d].get("usageItems", []))
            running += dg
            labels.append(d)
            g_series.append(round(dg, 2))
            n_series.append(round(dn, 2))
            cumulative.append(round(running, 2))
        trend = {
            "labels": labels, "gross": g_series, "net": n_series,
            "cumulative": cumulative,
        }

    return {
        "has_data": True,
        "days": days,
        "day": day,
        "scope": scope,
        "metrics": {
            "gross": gross, "net": net, "covered": gross - net, "credits": total_credits,
        },
        "fully_covered": net == 0 and gross > 0,
        "by_model": by_model,
        "model_chart": {
            "labels": [r["model"] for r in by_model],
            "gross": [round(r["gross"], 2) for r in by_model],
        },
        "trend": trend,
        "per_user": _per_user_day(source, day, gross),
    }


def _per_user_day(source: ReportsSource, day: str, day_gross: float) -> dict:
    """Per-user spend for a day: spenders sorted desc + summary counts."""
    docs = source.per_user_docs(day)
    spenders = []
    queried = 0
    for login, items in docs.items():
        if not items:
            continue
        queried += 1
        gross = sum(i.get("grossAmount", 0.0) for i in items)
        net = sum(i.get("netAmount", 0.0) for i in items)
        if gross <= 0:
            continue
        active = [i for i in items if i.get("grossAmount", 0.0) > 0]
        top = max(active, key=lambda i: i["grossAmount"])["model"] if active else "—"
        spenders.append({
            "user": login, "gross": gross, "net": net, "top_model": top,
            "share": (gross / day_gross) if day_gross else 0.0,
        })
    spenders.sort(key=lambda r: r["gross"], reverse=True)
    top_n = min(3, len(spenders))
    concentration = sum(r["share"] for r in spenders[:top_n])
    return {
        "rows": spenders,
        "queried": queried,
        "with_spend": len(spenders),
        "top_n": top_n,
        "concentration": concentration,
    }


# ---------------------------------------------------------------- weekly helpers
def _weekly_rows(source: ReportsSource) -> list[dict]:
    return wpu.rollup_weekly(source.weekly_records())


def _week_labels(rows: list[dict]) -> list[str]:
    # rows already sorted by week_label asc; keep first-seen order, de-duplicated.
    return list(dict.fromkeys(r["week_label"] for r in rows))


def weekly_view(source: ReportsSource, plan: str | None, week: str | None) -> dict:
    """Org weekly per-user allowance table for one ISO week."""
    all_rows = _weekly_rows(source)
    plan = resolve_plan(plan)
    if not all_rows:
        return {"has_data": False, "plans": plan_labels(), "plan": plan, "weeks": []}

    weeks = _week_labels(all_rows)
    week = week if week in weeks else weeks[-1]
    allowance = weekly_allowance(plan)

    wk = [r for r in all_rows if r["week_label"] == week]
    iso_year, iso_week = int(wk[0]["iso_year"]), int(wk[0]["iso_week"])
    mon, sun = wpu.week_span(iso_year, iso_week)

    rows = []
    for r in wk:
        credits_val = float(r["credits"])
        rows.append({
            "user": r["user"], "credits": credits_val,
            "pct": (credits_val / allowance) if allowance else 0.0,
            "remaining": allowance - credits_val,
            "top_model": r["top_model"], "day_count": int(r["day_count"]),
        })
    rows.sort(key=lambda x: x["credits"], reverse=True)
    over = sum(1 for x in rows if x["pct"] >= 1.0)

    return {
        "has_data": True,
        "plans": plan_labels(), "plan": plan, "allowance": allowance,
        "weeks": weeks, "week": week,
        "span": f"{mon:%a %d %b} – {sun:%a %d %b}",
        "active_users": len(rows),
        "rows": rows, "over": over,
    }


def user_view(  # pylint: disable=too-many-locals
    source: ReportsSource,
    login: str | None,
    plan: str | None,
    week: str | None = None,
) -> dict:
    """One user's personal usage, led by per-week usage vs the weekly limit.

    `week` selects which ISO week is in focus (defaults to the latest the user
    has data for); it drives the headline detail card and the daily breakdown.
    All figures are in AI credits.
    """
    plan = resolve_plan(plan)
    allowance = weekly_allowance(plan)
    limits = plan_limits(plan)
    base = {
        "plans": plan_labels(), "plan": plan, "allowance": allowance,
        "limits": limits, "login": (login or "").strip(),
    }
    if not base["login"]:
        return {**base, "searched": False}

    login_str = base["login"]
    records = source.weekly_records()
    urecs = sorted(
        (r for r in records if r["user"] == login_str), key=lambda r: r["day"]
    )
    if not urecs:
        return {**base, "searched": True, "found": False, "week": None}

    # ---- weekly history (the headline): one row per ISO week the user appears in
    all_rows = wpu.rollup_weekly(records)
    weekly_rows = []
    for r in (row for row in all_rows if row["user"] == login_str):
        credits_val = float(r["credits"])
        mon, sun = wpu.week_span(int(r["iso_year"]), int(r["iso_week"]))
        weekly_rows.append({
            "week_label": r["week_label"], "credits": credits_val,
            "pct": (credits_val / allowance) if allowance else 0.0,
            "remaining": allowance - credits_val, "day_count": int(r["day_count"]),
            "top_model": r["top_model"], "span": f"{mon:%d %b} – {sun:%d %b}",
        })
    weekly_rows.sort(key=lambda x: x["week_label"])
    weeks = [w["week_label"] for w in weekly_rows]
    weekly_chart = {
        "labels": weeks,
        "credits": [round(w["credits"], 1) for w in weekly_rows],
    }

    # ---- selected week drives the detail card + the daily breakdown
    selected = week if week in weeks else weeks[-1]
    current = next(w for w in weekly_rows if w["week_label"] == selected)

    week_recs = [r for r in urecs if wpu.iso_week_label(r["day"])[0] == selected]
    daily_rows = [
        {"day": r["day"], "credits": r["credits"], "usd": r["usd"]}
        for r in week_recs
    ]
    daily_chart = {
        "labels": [r["day"] for r in daily_rows],
        "credits": [round(r["credits"], 1) for r in daily_rows],
    }

    # ---- month-to-date: cumulative credits over the latest captured month
    latest_month = urecs[-1]["day"][:7]  # 'YYYY-MM'
    month_recs = [r for r in urecs if r["day"][:7] == latest_month]
    mtd_labels, mtd_cumulative, running = [], [], 0.0
    for r in month_recs:
        running += r["credits"]
        mtd_labels.append(r["day"])
        mtd_cumulative.append(round(running, 1))
    mtd = {
        "month": latest_month,
        "total_credits": running,
        "chart": {"labels": mtd_labels, "cumulative": mtd_cumulative},
    }

    return {
        **base,
        "searched": True, "found": True,
        "weeks": weeks, "weekly": weekly_rows, "weekly_chart": weekly_chart,
        "week": selected, "span": current["span"],
        "used": current["credits"], "remaining": current["remaining"],
        "pct": current["pct"], "day_count": current["day_count"],
        "top_model": current["top_model"],
        "daily": daily_rows, "daily_chart": daily_chart,
        "mtd": mtd,
    }
