"""Pure logic for the weekly per-user AI-credit view in ai_credits_app.py.

Kept free of Streamlit so it can be imported and unit-tested directly. Reads the
per-user billing JSON that download-billing.sh writes to
reports/<date>/billing/per-user/<login>.json.
"""

import glob
import json
import os
from collections import defaultdict
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


def rollup_weekly(records: list[dict]) -> list[dict]:
    """Sum per-(week, user) credits/usd from per-day records.

    records: [{"day","user","credits","usd","per_model": {model: credits}}, ...]
    Returns one dict per (week_label, user) with merged per-model sums, the top
    model by credits, and the count of distinct days the user appears in, sorted
    by week (ascending) then credits (descending). Empty input -> empty list.
    """
    agg: dict[tuple[str, str], dict] = {}
    for r in records:
        label, iso_year, iso_week = iso_week_label(r["day"])
        key = (label, r["user"])
        bucket = agg.get(key)
        if bucket is None:
            bucket = {
                "week_label": label, "iso_year": iso_year, "iso_week": iso_week,
                "user": r["user"], "credits": 0.0, "usd": 0.0,
                "days": set(), "per_model": defaultdict(float),
            }
            agg[key] = bucket
        bucket["credits"] += r["credits"]
        bucket["usd"] += r["usd"]
        bucket["days"].add(r["day"])
        for model, cr in r.get("per_model", {}).items():
            bucket["per_model"][model] += cr

    rows = []
    for bucket in agg.values():
        per_model = dict(bucket["per_model"])
        top_model = max(per_model, key=per_model.get) if per_model else "—"
        rows.append({
            "week_label": bucket["week_label"], "iso_year": bucket["iso_year"],
            "iso_week": bucket["iso_week"], "user": bucket["user"],
            "credits": bucket["credits"], "usd": bucket["usd"],
            "day_count": len(bucket["days"]), "top_model": top_model,
            "per_model": per_model,
        })

    rows.sort(key=lambda x: (x["week_label"], -x["credits"]))
    return rows


PER_USER_GLOB = "reports/*/billing/per-user/*.json"


def _day_from_per_user_path(path: str) -> str:
    # reports/2026-06-01/billing/per-user/alice.json -> 2026-06-01
    parts = path.replace("\\", "/").split("/")
    return parts[parts.index("reports") + 1]


def record_from_items(day: str, user: str, items: list[dict]) -> dict | None:
    """One (day, user) record with usage summed per model.

    Returns None when there are no items or no positive credit usage, so callers
    can skip non-spenders. Mirrors the shape rollup_weekly expects.
    """
    if not items:
        return None
    per_model: dict[str, float] = defaultdict(float)
    credits = 0.0
    usd = 0.0
    for it in items:
        cr = it.get("grossQuantity", 0.0)
        per_model[it["model"]] += cr
        credits += cr
        usd += it.get("grossAmount", 0.0)
    if credits <= 0:
        return None
    return {
        "day": day, "user": user,
        "credits": credits, "usd": usd, "per_model": dict(per_model),
    }


def load_weekly_records(glob_pattern: str = PER_USER_GLOB) -> list[dict]:
    """One record per (day, user) with usage, summed per model. Skips empties."""
    records = []
    for path in sorted(glob.glob(glob_pattern)):
        login = os.path.splitext(os.path.basename(path))[0]
        with open(path) as f:
            items = json.load(f).get("usageItems", [])
        rec = record_from_items(_day_from_per_user_path(path), login, items)
        if rec is not None:
            records.append(rec)
    return records
