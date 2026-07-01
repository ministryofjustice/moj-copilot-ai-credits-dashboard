"""View-model builders for the AI-credits dashboard.

Turns a `ReportsSource` into plain, JSON-serialisable structures the templates
and Chart.js consume. No Flask and no Streamlit here — just data shaping — so it
stays unit-testable and backend-agnostic.

Ported from copilot-daily/ai_credits_app.py (the `load_days` / `load_per_user` /
`load_weekly_rollup` loaders + the per-tab layout maths), minus Streamlit and
minus `@st.cache_data`.
"""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, timedelta

from app.main.services import weekly_per_user as wpu
from app.main.services.reports_source import ReportsSource

# How many of the biggest spenders the local-dev example user is drawn from.
EXAMPLE_POOL_SIZE = 10


def example_login(source: ReportsSource) -> str:
    """A random login from the top spenders — a stand-in user for local dev.

    No real login is hard-coded; one is picked at runtime from the biggest
    `EXAMPLE_POOL_SIZE` spenders so the My usage page renders with real data.
    Returns "" when there is no data.
    """
    totals: dict[str, float] = defaultdict(float)
    for r in source.user_rows():
        totals[r["user_login"]] += r["credits"]
    if not totals:
        return ""
    top = sorted(totals, key=totals.get, reverse=True)[:EXAMPLE_POOL_SIZE]
    return random.choice(top)


# Per-seat allowance maths. Credits bill at $0.01 each ($1 == 100 credits). The
# included allowance is monthly; spread across an average ISO week (month / 4.33)
# to get the weekly denominator for the "% used / remaining" view.
CREDITS_PER_USD = 100.0
WEEKS_PER_MONTH = 4.33
# Selectable monthly per-seat AI-credit budgets (USD).
PLAN_TIERS_USD_PER_MONTH = {"$70 / month": 70.0, "$39 / month": 39.0}
DEFAULT_PLAN = "$70 / month"
DEFAULT_SEATS = 405
# The dataset has no scope column; the enterprise it covers is fixed.
ENTERPRISE = "ministryofjustice"


def _user_records(source: ReportsSource) -> list[dict]:
    """user_rows reshaped to the {day, user, credits} the week/pool maths expect."""
    return [{"day": r["day"], "user": r["user_login"], "credits": r["credits"]}
            for r in source.user_rows()]


def resolve_seats(raw) -> int:
    """Coerce a seat-count query value to a positive int, else DEFAULT_SEATS."""
    try:
        seats = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SEATS
    return seats if seats > 0 else DEFAULT_SEATS


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


# --------------------------------------------------------------- heatmap helpers
HEATMAP_WEEKS = 9  # rolling window (~2 months) for the user usage heatmap

# Colour ramp for the heatmap: grey (no usage) -> greens (within budget) ->
# graduated reds (over budget), so a day at 108% reads lighter than one at 600%.
HEATMAP_LEVELS = [
    {"level": 0, "colour": "#ebedee", "label": "None"},
    {"level": 1, "colour": "#cce2d8", "label": "<25%"},
    {"level": 2, "colour": "#85bfa3", "label": "25–50%"},
    {"level": 3, "colour": "#00703c", "label": "50–100%"},
    {"level": 4, "colour": "#f4a18f", "label": "100–150%"},
    {"level": 5, "colour": "#d4351c", "label": "150–300%"},
    {"level": 6, "colour": "#8e1b0e", "label": "≥300%"},
]


_HEATMAP_THRESHOLDS = [(0.25, 1), (0.50, 2), (1.0, 3), (1.5, 4), (3.0, 5)]


def _heatmap_level(pct: float) -> int:
    if pct <= 0:
        return 0
    for threshold, level in _HEATMAP_THRESHOLDS:
        if pct < threshold:
            return level
    return 6


def _usage_calendar(urecs: list[dict], daily_allowance: float,  # pylint: disable=too-many-locals
                    weeks: int = HEATMAP_WEEKS) -> dict:
    """Rolling-window day grid for the user heatmap (columns=ISO weeks, rows=Mon→Sun).

    Anchored so the rightmost column is the latest record's ISO week. Days with no
    record render as level 0 (no usage). Mapping is by calendar date, not index.
    """
    if not urecs:
        return {"weeks": [], "month_labels": [], "max_credits": 0.0,
                "levels": HEATMAP_LEVELS}

    credits_by_day = {r["day"]: r["credits"] for r in urecs}
    latest = date.fromisoformat(urecs[-1]["day"])
    # Monday of the latest record's ISO week, then back (weeks-1) Mondays = grid start.
    last_monday = latest - timedelta(days=latest.weekday())
    start = last_monday - timedelta(weeks=weeks - 1)

    grid, month_labels = [], []
    seen_month = None
    for col in range(weeks):
        col_start = start + timedelta(weeks=col)
        column = []
        for row in range(7):
            d = col_start + timedelta(days=row)
            iso = d.isoformat()
            credits_val = credits_by_day.get(iso, 0.0)
            pct = (credits_val / daily_allowance) if daily_allowance else 0.0
            column.append({
                "day": iso,
                "credits": round(credits_val, 1),
                "pct": pct,
                "level": _heatmap_level(pct),
                "label": (f"{d:%-d %b %Y}: {credits_val:.1f} credits "
                          f"({pct * 100:.0f}% of daily allowance)"
                          if credits_val > 0 else f"{d:%-d %b %Y}: no usage"),
            })
        grid.append(column)
        if col_start.month != seen_month:
            month_labels.append({"col": col, "text": f"{col_start:%b}"})
            seen_month = col_start.month

    return {
        "weeks": grid,
        "month_labels": month_labels,
        "max_credits": max(credits_by_day.values()),
        "levels": HEATMAP_LEVELS,
    }


# ----------------------------------------------------------------- daily helpers
def _agg_by(rows: list[dict], field: str, total: float) -> list[dict]:
    """Sum credits by `field` over model rows, spenders only, descending."""
    agg: dict[str, float] = defaultdict(float)
    for r in rows:
        agg[r[field]] += r["credits"]
    out = [{field: k, "credits": v, "share": (v / total) if total else 0.0}
           for k, v in agg.items() if v > 0]
    out.sort(key=lambda r: r["credits"], reverse=True)
    return out


def _org_rollup(day_total: dict[str, float], day: str) -> dict:
    """Org Last-day / WTD / MTD credits, anchored to (and counting up to) `day`."""
    label = wpu.iso_week_label(day)[0]
    wtd = sum(c for d, c in day_total.items()
              if wpu.iso_week_label(d)[0] == label and d <= day)
    month = day[:7]
    mtd = sum(c for d, c in day_total.items() if d[:7] == month and d <= day)
    return {"last_day": day_total[day], "wtd": wtd, "mtd": mtd,
            "week_label": label, "month": month}


def daily_view(source: ReportsSource, day: str | None = None) -> dict:  # pylint: disable=too-many-locals
    """Everything the Daily admin page needs for one day, plus the MTD trend.

    Org-level credits only (the data has no gross/net/coverage). Adds a model-family
    split, an auto-routed-vs-chosen split, and the org Last-day/WTD/MTD rollup.
    """
    mrows = source.model_rows()
    if not mrows:
        return {"has_data": False, "days": []}

    day_total: dict[str, float] = defaultdict(float)
    for r in mrows:
        day_total[r["day"]] += r["credits"]
    days = sorted(day_total)
    day = day if day in day_total else days[-1]

    day_rows = [r for r in mrows if r["day"] == day]
    total = sum(r["credits"] for r in day_rows)
    by_model = _agg_by(day_rows, "model", total)
    by_family = _agg_by(day_rows, "model_family", total)
    routed = sum(r["credits"] for r in day_rows if r["routed"])
    chosen = total - routed

    # Month-to-date trend (only meaningful with 2+ days captured).
    trend = None
    if len(days) >= 2:
        running, totals, cumulative = 0.0, [], []
        for d in days:
            running += day_total[d]
            totals.append(round(day_total[d], 2))
            cumulative.append(round(running, 2))
        trend = {"labels": days, "totals": totals, "cumulative": cumulative}

    per_user = _per_user_day(source, day, total)

    return {
        "has_data": True,
        "days": days,
        "day": day,
        "scope": ENTERPRISE,
        "metrics": {"credits": total, "usd": total / CREDITS_PER_USD,
                    "spenders": per_user["with_spend"], "models": len(by_model)},
        "by_model": by_model,
        "model_chart": {
            "labels": [r["model"] for r in by_model],
            "credits": [round(r["credits"], 2) for r in by_model],
        },
        "family_chart": {
            "labels": [r["model_family"] for r in by_family],
            "credits": [round(r["credits"], 2) for r in by_family],
        },
        "routed_chart": {
            "labels": ["Auto-routed", "Explicitly chosen"],
            "credits": [round(routed, 2), round(chosen, 2)],
        },
        "trend": trend,
        "rollup": _org_rollup(day_total, day),
        "per_user": per_user,
    }


def _per_user_day(source: ReportsSource, day: str, day_total: float) -> dict:
    """Per-user spend for a day: spenders sorted desc + concentration of the top few."""
    rows = [r for r in source.user_rows() if r["day"] == day and r["credits"] > 0]
    spenders = [{"user": r["user_login"], "credits": r["credits"],
                 "share": (r["credits"] / day_total) if day_total else 0.0}
                for r in rows]
    spenders.sort(key=lambda r: r["credits"], reverse=True)
    top_n = min(3, len(spenders))
    return {
        "rows": spenders,
        "with_spend": len(spenders),
        "top_n": top_n,
        "concentration": sum(r["share"] for r in spenders[:top_n]),
    }


# ---------------------------------------------------------------- weekly helpers
def _resolve_label(selected: str | None, labels: list[str]) -> str:
    """Pick a period label from `labels`, matching case-insensitively.

    The govuk select macro lowercases every option `value`, so the browser
    submits e.g. 'week=2026-w23' for the option labelled '2026-W23'. Match
    ignoring case so the selection resolves to the real label; fall back to the
    most recent label when there's no match (or nothing selected).
    """
    if selected:
        for label in labels:
            if label.lower() == selected.lower():
                return label
    return labels[-1]


def _weekly_rows(source: ReportsSource) -> list[dict]:
    return wpu.rollup_weekly(_user_records(source))


def _week_labels(rows: list[dict]) -> list[str]:
    # rows already sorted by week_label asc; keep first-seen order, de-duplicated.
    return list(dict.fromkeys(r["week_label"] for r in rows))


def _week_ranges(rows: list[dict]) -> dict[str, str]:
    """Map each ISO week label to its compact 'from–to' date range."""
    return {
        r["week_label"]: wpu.format_week_range(int(r["iso_year"]), int(r["iso_week"]))
        for r in rows
    }


# ----------------------------------------------------------------- pooled helpers
TIER_COLOURS = {
    "Power": "#d4351c",
    "Heavy": "#f47738",
    "Typical": "#1d70b8",
    "Light": "#00703c",
    "Overage (billed extra)": "#85230c",
    "Unused pool": "#b1b4b6",
}


def _record_period_key(day: str, period: str) -> str:
    """ISO-week label or calendar-month label for a day, per the period type."""
    if period == "weekly":
        return wpu.iso_week_label(day)[0]
    return wpu.month_label(day)


def _period_text(key: str, period: str) -> str:
    """Selector/headline text: '2026-W23 (1–7 Jun)' or 'Jun 2026'."""
    if period == "weekly":
        iso_year, iso_week = key.split("-W")
        return f"{key} ({wpu.format_week_range(int(iso_year), int(iso_week))})"
    return wpu.format_month_label(key)


def pooled_view(source: ReportsSource, period: str | None, key: str | None,  # pylint: disable=too-many-locals
                plan: str | None, seats) -> dict:
    """Pooled-billing treemap data for one ISO week or calendar month.

    pool = seats * per-seat allowance for the period; covered usage is split by
    user spend-tier and scaled to min(gross, pool); the remainder is an
    'Unused pool' tile (within budget) or an 'Overage' tile (over budget). All
    figures are AI credits.
    """
    period = "weekly" if period == "weekly" else "monthly"
    plan = resolve_plan(plan)
    seats = resolve_seats(seats)
    records = _user_records(source)
    keys = sorted({_record_period_key(r["day"], period) for r in records})

    base = {
        "period": period, "plans": plan_labels(), "plan": plan, "seats": seats,
        "periods": keys,
    }
    if not keys:
        return {**base, "has_data": False, "key": None}

    key = _resolve_label(key, keys)
    user_credits: dict[str, float] = {}
    for r in records:
        if _record_period_key(r["day"], period) == key:
            user_credits[r["user"]] = user_credits.get(r["user"], 0.0) + float(r["credits"])

    allowance = plan_limits(plan)[period]
    pool = seats * allowance
    gross = sum(user_credits.values())
    overage = max(0.0, gross - pool)
    headroom = pool - gross
    total = max(pool, gross)
    covered_scale = (min(gross, pool) / gross) if gross else 0.0

    tiers = wpu.assign_tiers(user_credits)
    tier_gross = {t: 0.0 for t in wpu.TIER_ORDER}
    tier_users = {t: 0 for t in wpu.TIER_ORDER}
    for user, credits_val in user_credits.items():
        tier_gross[tiers[user]] += credits_val
        tier_users[tiers[user]] += 1

    tiles = [
        {"label": f"{t} users", "name": t,
         "amount": round(tier_gross[t] * covered_scale, 1),
         "users": tier_users[t], "colour": TIER_COLOURS[t]}
        for t in wpu.TIER_ORDER
    ]
    if overage > 0:
        tiles.append({"label": "Overage (billed extra)", "name": "Overage",
                      "amount": round(overage, 1), "users": None,
                      "colour": TIER_COLOURS["Overage (billed extra)"]})
    elif headroom > 0:
        tiles.append({"label": "Unused pool", "name": "Unused pool",
                      "amount": round(headroom, 1), "users": None,
                      "colour": TIER_COLOURS["Unused pool"]})

    return {
        **base,
        "has_data": True,
        "key": key,
        "span": _period_text(key, period),
        "period_options": [{"value": k, "text": _period_text(k, period)} for k in keys],
        "allowance": allowance,
        "active_users": len(user_credits),
        "metrics": {"pool": pool, "gross": gross, "overage": overage,
                    "total": total, "headroom": headroom},
        "tiles": tiles,
        "treemap": {"type": "treemap",
                    "root": f"Total bill {total:,.0f} credits (${total / 100:,.0f})",
                    "total": total, "tiles": tiles},
    }


def weekly_view(source: ReportsSource, plan: str | None, week: str | None) -> dict:  # pylint: disable=too-many-locals
    """Org weekly per-user allowance table for one ISO week."""
    all_rows = _weekly_rows(source)
    plan = resolve_plan(plan)
    if not all_rows:
        return {"has_data": False, "plans": plan_labels(), "plan": plan, "weeks": []}

    weeks = _week_labels(all_rows)
    week = _resolve_label(week, weeks)
    allowance = weekly_allowance(plan)

    wk = [r for r in all_rows if r["week_label"] == week]
    iso_year, iso_week = int(wk[0]["iso_year"]), int(wk[0]["iso_week"])
    mon, sun = wpu.week_span(iso_year, iso_week)
    week_ranges = _week_ranges(all_rows)

    rows = []
    for r in wk:
        credits_val = float(r["credits"])
        rows.append({
            "user": r["user"], "credits": credits_val,
            "pct": (credits_val / allowance) if allowance else 0.0,
            "remaining": allowance - credits_val,
            "day_count": int(r["day_count"]),
        })
    rows.sort(key=lambda x: x["credits"], reverse=True)
    over = sum(1 for x in rows if x["pct"] >= 1.0)

    return {
        "has_data": True,
        "plans": plan_labels(), "plan": plan, "allowance": allowance,
        "weeks": weeks, "week": week,
        "week_ranges": week_ranges,
        "span": f"{mon:%a %d %b} – {sun:%a %d %b}",
        "active_users": len(rows),
        "rows": rows, "over": over,
    }


def user_view(  # pylint: disable=too-many-locals
    source: ReportsSource,
    login: str | None,
    plan: str | None,
    month: str | None = None,
) -> dict:
    """One user's personal usage, led by per-week usage vs the weekly limit.

    `month` selects which calendar month is in focus (defaults to the latest the
    user has data for); it drives the per-week cost-stats table, the per-week
    bar chart, and the cumulative chart. A week is attributed to the month its
    Monday falls in, so a week straddling a boundary stays whole. All figures
    are in AI credits.
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
    records = _user_records(source)
    urecs = sorted(
        (r for r in records if r["user"] == login_str), key=lambda r: r["day"]
    )
    if not urecs:
        return {**base, "searched": True, "found": False, "month": None}

    # ---- weekly history (the headline): one row per ISO week the user appears in
    all_rows = wpu.rollup_weekly(records)
    weekly_rows = []
    for r in (row for row in all_rows if row["user"] == login_str):
        credits_val = float(r["credits"])
        iso_year, iso_week = int(r["iso_year"]), int(r["iso_week"])
        mon, sun = wpu.week_span(iso_year, iso_week)
        weekly_rows.append({
            "week_label": r["week_label"], "credits": credits_val,
            "pct": (credits_val / allowance) if allowance else 0.0,
            "remaining": allowance - credits_val, "day_count": int(r["day_count"]),
            "span": f"{mon:%d %b} – {sun:%d %b}",
            "range": wpu.format_week_range(iso_year, iso_week),
            # A week belongs to the month its Monday falls in (so it stays whole).
            "month": f"{mon:%Y-%m}",
        })
    weekly_rows.sort(key=lambda x: x["week_label"])
    weeks = [w["week_label"] for w in weekly_rows]
    week_ranges = _week_ranges(all_rows)
    weekly_chart = {
        "labels": [f"{w} ({week_ranges[w]})" for w in weeks],
        "credits": [round(w["credits"], 1) for w in weekly_rows],
    }

    # ---- selected month drives the per-week cost stats (table + bar) and the
    # cumulative chart; default to the latest month the user has data for.
    months = sorted({w["month"] for w in weekly_rows})
    selected_month = month if month in months else months[-1]
    month_weeks = [w for w in weekly_rows if w["month"] == selected_month]
    month_week_labels = {w["week_label"] for w in month_weeks}
    month_weekly_chart = {
        "labels": [f"{w['week_label']} ({w['range']})" for w in month_weeks],
        "credits": [round(w["credits"], 1) for w in month_weeks],
    }

    # ---- cumulative credits across the selected month's weeks. Keyed on whole
    # weeks (not calendar days) so a straddling week's spill-over days stay with
    # the month its Monday belongs to, matching the table and bar above.
    month_day_recs = [
        r for r in urecs if wpu.iso_week_label(r["day"])[0] in month_week_labels
    ]
    cum_labels, cum_values, running = [], [], 0.0
    for r in month_day_recs:
        running += r["credits"]
        cum_labels.append(r["day"])
        cum_values.append(round(running, 1))
    month_cumulative = {
        "month": selected_month,
        "month_label": wpu.format_month_label(selected_month),
        "total_credits": running,
        "chart": {"labels": cum_labels, "cumulative": cum_values},
    }

    # ---- Last-day / Week-to-date / Month-to-date, anchored to the latest day.
    # The plan is weekly limits, so WTD-vs-weekly-allowance is the teaching number.
    summary = _user_summary(urecs, allowance, limits)

    return {
        **base,
        "searched": True, "found": True,
        "weeks": weeks, "weekly": weekly_rows, "weekly_chart": weekly_chart,
        "week_ranges": week_ranges,
        "months": months, "month": selected_month,
        "month_label": wpu.format_month_label(selected_month),
        "month_options": [{"value": m, "text": wpu.format_month_label(m)}
                          for m in months],
        "month_weeks": month_weeks, "month_weekly_chart": month_weekly_chart,
        "month_cumulative": month_cumulative,
        "summary": summary,
        "calendar": _usage_calendar(urecs, limits["daily"]),
    }


def _user_summary(urecs: list[dict], allowance: float, limits: dict) -> dict:
    """Last-day / WTD / MTD figures for a user, anchored to their latest day.

    `urecs` is the user's per-day records sorted ascending by day. WTD/MTD are
    running totals of the latest ISO week / calendar month (the data only runs to
    the latest day, so "to date" falls straight out of summing those records).
    """
    as_of = urecs[-1]["day"]
    last_day = sum(r["credits"] for r in urecs if r["day"] == as_of)
    wtd_label = wpu.iso_week_label(as_of)[0]
    wtd_recs = [r for r in urecs if wpu.iso_week_label(r["day"])[0] == wtd_label]
    wtd = sum(r["credits"] for r in wtd_recs)
    month = as_of[:7]
    mtd = sum(r["credits"] for r in urecs if r["day"][:7] == month)
    return {
        "as_of": as_of,
        "last_day": {"credits": last_day, "allowance": limits["daily"],
                     "pct": (last_day / limits["daily"]) if limits["daily"] else 0.0},
        "wtd": {"credits": wtd, "allowance": allowance,
                "remaining": allowance - wtd, "week_label": wtd_label,
                "days": len({r["day"] for r in wtd_recs}),
                "pct": (wtd / allowance) if allowance else 0.0},
        "mtd": {"credits": mtd, "allowance": limits["monthly"], "month": month,
                "pct": (mtd / limits["monthly"]) if limits["monthly"] else 0.0},
    }
