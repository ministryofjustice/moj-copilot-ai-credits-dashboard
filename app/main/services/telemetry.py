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
