"""Pure logic for the weekly per-user AI-credit view.

Kept free of Flask so it can be imported and unit-tested directly. Operates on
plain per-user daily records (`{day, user, credits}`) sourced from the
`credits_by_user` parquet table — no per-model breakdown exists in this data.
"""

from datetime import date


def iso_week_label(day_str: str) -> tuple[str, int, int]:
    """'2026-06-01' -> ('2026-W23', 2026, 23) using ISO (Mon-Sun) weeks."""
    iso_year, iso_week, _ = date.fromisoformat(day_str).isocalendar()
    return f"{iso_year}-W{iso_week:02d}", iso_year, iso_week


def week_span(iso_year: int, iso_week: int) -> tuple[date, date]:
    """ISO (year, week) -> (Monday, Sunday) dates for that week."""
    monday = date.fromisocalendar(iso_year, iso_week, 1)
    sunday = date.fromisocalendar(iso_year, iso_week, 7)
    return monday, sunday


def format_week_range(iso_year: int, iso_week: int) -> str:
    """Compact 'from–to' range for an ISO week, e.g. '1–7 Jun'.

    Drops the repeated month when the week stays within one (e.g. '1–7 Jun'),
    and spells out both months when it straddles a boundary (e.g. '29 Jun – 5
    Jul', '29 Dec – 4 Jan'). Years are omitted to keep it short.
    """
    monday, sunday = week_span(iso_year, iso_week)
    if monday.month == sunday.month:
        return f"{monday.day}–{sunday.day} {monday:%b}"
    return f"{monday.day} {monday:%b} – {sunday.day} {sunday:%b}"


def month_label(day_str: str) -> str:
    """'2026-06-01' -> '2026-06' (calendar month)."""
    return day_str[:7]


def format_month_label(month_str: str) -> str:
    """'2026-06' -> 'Jun 2026'."""
    first = date.fromisoformat(f"{month_str}-01")
    return f"{first:%b %Y}"


TIER_ORDER = ["Power", "Heavy", "Typical", "Light"]


def assign_tiers(user_credits: dict[str, float]) -> dict[str, str]:
    """Label each user Power/Heavy/Typical/Light by their credit-share rank.

    Mirrors the copilotquota treemap: rank users by credits (descending),
    fraction = rank / n, then bin by [0, .05, .20, .75, 1] into Power (top 5%),
    Heavy (next 15%), Typical (middle 55%), Light (bottom 25%). Ties keep input
    order (Python's sort is stable). Empty input -> empty dict.
    """
    n = len(user_credits)
    if n == 0:
        return {}
    ordered = sorted(user_credits, key=lambda u: user_credits[u], reverse=True)
    tiers: dict[str, str] = {}
    for i, user in enumerate(ordered):
        frac = (i + 1) / n
        if frac <= 0.05:
            tiers[user] = "Power"
        elif frac <= 0.20:
            tiers[user] = "Heavy"
        elif frac <= 0.75:
            tiers[user] = "Typical"
        else:
            tiers[user] = "Light"
    return tiers


def rollup_weekly(records: list[dict]) -> list[dict]:
    """Sum per-(week, user) credits from per-day {day, user, credits} records.

    Returns one dict per (week_label, user) with summed credits and the count of
    distinct days the user appears in, sorted by week (ascending) then credits
    (descending). Empty input -> empty list.
    """
    agg: dict[tuple[str, str], dict] = {}
    for r in records:
        label, iso_year, iso_week = iso_week_label(r["day"])
        key = (label, r["user"])
        bucket = agg.get(key)
        if bucket is None:
            bucket = {
                "week_label": label, "iso_year": iso_year, "iso_week": iso_week,
                "user": r["user"], "credits": 0.0, "days": set(),
            }
            agg[key] = bucket
        bucket["credits"] += r["credits"]
        bucket["days"].add(r["day"])

    rows = [{
        "week_label": b["week_label"], "iso_year": b["iso_year"],
        "iso_week": b["iso_week"], "user": b["user"],
        "credits": b["credits"], "day_count": len(b["days"]),
    } for b in agg.values()]
    rows.sort(key=lambda x: (x["week_label"], -x["credits"]))
    return rows
