"""What a person did with Copilot in one month, as page-ready figures.

Pure functions over the row lists `ReportsSource` returns: no file access, no
network, no Flask. That is what lets every number here be tested from plain
dictionaries.

Three rules from the pipeline's own dataset documentation are enforced here,
because breaking any of them produces a plausible-looking wrong number:

* A null count is not a zero. GitHub sends a reduced record for roughly a
  quarter of person-days, carrying no activity data at all. Such a day
  contributes nothing to a total and is never counted as a day of no activity.
* No rate is computed across all features. GitHub excludes agent edits from
  `loc_suggested_to_add_sum` but includes them in `loc_added_sum`, so a
  lines-kept ratio over everything exceeds 100 per cent. This module computes
  no such rate.
* Acceptance is not reported per mode. Agent features apply code without a
  discrete accept step, so their acceptance counts are near zero and a rate
  would misrepresent people who work mainly through agents.
"""

from __future__ import annotations

VOLUME_FIELDS = ("interactions", "suggested", "accepted",
                 "lines_added", "lines_deleted")


def _total(rows: list[dict], field: str) -> int:
    """Sum a count column, skipping nulls rather than reading them as zero."""
    return sum(row[field] for row in rows if row.get(field) is not None)


def volume(user_rows: list[dict]) -> dict:
    """Month totals, plus how much of the month actually carried telemetry.

    `days_with_telemetry` is reported alongside the totals so the page can say
    what the totals cover. Without it a month where GitHub sent data on four
    days looks the same as a quiet month.
    """
    figures = {field: _total(user_rows, field) for field in VOLUME_FIELDS}
    figures["days_recorded"] = len(user_rows)
    figures["days_with_telemetry"] = sum(
        1 for row in user_rows if row.get("has_telemetry") is True)
    return figures


def review_activity(user_rows: list[dict]) -> dict:
    """Days Copilot reviewed this person's code, split by who asked for it.

    Only an explicit True counts. Null means no telemetry arrived that day and
    is reported separately rather than being read as "no review happened".
    """
    return {
        "requested": sum(1 for r in user_rows
                         if r.get("review_requested") is True),
        "automatic": sum(1 for r in user_rows
                         if r.get("review_automatic") is True),
        "days_recorded": len(user_rows),
        "days_without_telemetry": sum(
            1 for r in user_rows if r.get("has_telemetry") is not True),
    }


def _grouped_totals(rows: list[dict], key_of) -> dict:
    """Sum `suggested` and `lines_added` per group, skipping nulls and any row
    whose key is None."""
    totals: dict = {}
    for row in rows:
        key = key_of(row)
        if key is None:
            continue
        entry = totals.setdefault(key, {"suggested": 0, "lines_added": 0})
        for field in ("suggested", "lines_added"):
            value = row.get(field)
            if value is not None:
                entry[field] += value
    return totals


def mode_split(activity_rows: list[dict]) -> list[dict]:
    """How the person's activity divides across the Copilot surfaces.

    Grouped by the `mode` column the pipeline already derives from `feature`,
    so the dashboard does not invent a second grouping. Ranked by suggestions
    offered, with each mode's share of the month's suggestions. No acceptance
    figure: agent features apply code without a discrete accept step, so a
    per-mode acceptance rate would make agent users look inactive.
    """
    totals = _grouped_totals(activity_rows, lambda row: row.get("mode"))
    grand_total = sum(entry["suggested"] for entry in totals.values())
    modes = [
        {"mode": mode,
         "suggested": entry["suggested"],
         "lines_added": entry["lines_added"],
         "share": (entry["suggested"] / grand_total) if grand_total else 0.0}
        for mode, entry in totals.items()
    ]
    modes.sort(key=lambda m: (-m["suggested"], m["mode"]))
    return modes
