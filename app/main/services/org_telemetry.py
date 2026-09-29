"""What the whole organisation did with Copilot in one month, as page-ready
figures.

The org-wide twin of `telemetry.py`, which serves one person. Pure functions
over the rows `ReportsSource.org_telemetry_*_rows` return: no file access, no
network, no Flask.

The rules in `telemetry.py` apply here unchanged, and its helpers are
imported rather than copied: a null count is not a zero, and the only
acceptance rate is inline completion's, shown only where `_rate` allows it.

The rows carry `user_login` so people can be counted. Nothing this module
returns contains a login.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.main.services import weekly_per_user as wpu
from app.main.services.ai_credits import _full_day_label, _resolve_label
from app.main.services.telemetry import (
    INLINE_COMPLETION_MODE,
    _grouped_totals,
    _rate,
    _rows_in_mode,
    _total,
    agent_lines_added,
    display_language,
    inline_completion,
    month_bounds,
)

# Person-day counts that show use of Copilot when above zero.
ACTIVE_COUNTS = ("interactions", "suggested", "credits")

# Person-day flags that show use of Copilot when True.
ACTIVE_FLAGS = ("used_chat", "used_agent", "used_cli", "used_app",
                "used_coding_agent", "used_cloud_agent",
                "review_requested", "review_automatic")

# The lines of the capability-share chart: (legend label, flag).
CAPABILITY_LINES = (
    ("Chat", "used_chat"),
    ("Agent mode", "used_agent"),
    ("Copilot CLI", "used_cli"),
    ("Coding agent", "used_coding_agent"),
    ("Code review requested", "review_requested"),
)


def is_active(row: dict) -> bool:
    """True if this person-day shows any use of Copilot.

    Null counts and null flags do not count: GitHub sends a reduced record on
    some days, and a missing value is not evidence of use."""
    if any((row.get(field) or 0) > 0 for field in ACTIVE_COUNTS):
        return True
    return any(row.get(flag) is True for flag in ACTIVE_FLAGS)


def month_days(user_rows: list[dict]) -> list[str]:
    """The days that have at least one person row, in order."""
    return sorted({row["day"] for row in user_rows})


def _rows_by_day(rows: list[dict]) -> dict[str, list[dict]]:
    by_day: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_day[row["day"]].append(row)
    return by_day


def _day_axis(days: list[str]) -> dict:
    """Day numbers on the axis and full dates in the tooltip, as the credit
    charts in ai_credits.py do."""
    return {"labels": [str(int(day[8:10])) for day in days],
            "tooltip_labels": [_full_day_label(day) for day in days]}


def language_totals(activity_rows: list[dict]) -> list[dict]:
    """Counts per display language name, most accepted suggestions first.

    Aliases are folded and non-languages dropped by `display_language`, the
    same mapping the personal page uses."""
    totals = _grouped_totals(
        activity_rows, lambda row: display_language(row.get("language")))
    ranked = [{"language": name,
               "suggested": entry["suggested"],
               "accepted": entry["accepted"],
               "lines_added": entry["lines_added"]}
              for name, entry in totals.items()]
    ranked.sort(key=lambda lang: (-lang["accepted"], lang["language"]))
    return ranked


def tiles(user_rows: list[dict], activity_rows: list[dict]) -> dict:
    """The figures in the summary tiles at the top of the page."""
    days = month_days(user_rows)
    inline = inline_completion(activity_rows)
    languages = language_totals(activity_rows)
    return {
        "days": len(days),
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "people_active": len({row["user_login"] for row in user_rows
                              if is_active(row)}),
        "seats_seen": len({row["user_login"] for row in user_rows}),
        "suggested": _total(user_rows, "suggested"),
        "inline_accepted": inline["accepted"],
        "inline_suggested": inline["suggested"],
        "inline_acceptance_rate": inline["acceptance_rate"],
        "lines_added": _total(user_rows, "lines_added"),
        "agent_lines_added": agent_lines_added(activity_rows),
        "inline_lines_kept": inline["lines_added"],
        "inline_lines_suggested": inline["lines_suggested_added"],
        "inline_keep_rate": _rate(inline["lines_added"],
                                  inline["lines_suggested_added"]),
        "interactions": _total(user_rows, "interactions"),
        "requests": (_total(user_rows, "cli_requests")
                     + _total(user_rows, "app_requests")),
        "prompts": (_total(user_rows, "cli_prompts")
                    + _total(user_rows, "app_prompts")),
        "languages_seen": len(languages),
        "top_language": languages[0]["language"] if languages else None,
    }


def capability_share(user_rows: list[dict], days: list[str]) -> dict:
    """Per day, the percentage of that day's active people with each
    capability flag set. A day with no active people has no value."""
    active_by_day = _rows_by_day([row for row in user_rows if is_active(row)])
    series = []
    for label, flag in CAPABILITY_LINES:
        data = []
        for day in days:
            active = active_by_day.get(day, [])
            if not active:
                data.append(None)
                continue
            using = sum(1 for row in active if row.get(flag) is True)
            data.append(round(100 * using / len(active), 1))
        series.append({"label": label, "data": data})
    return {**_day_axis(days), "series": series}


def daily_activity(user_rows: list[dict], days: list[str]) -> dict:
    """Suggestions, acceptances and interactions per day, across all modes."""
    by_day = _rows_by_day(user_rows)
    return {
        **_day_axis(days),
        "suggested": [_total(by_day.get(d, []), "suggested") for d in days],
        "accepted": [_total(by_day.get(d, []), "accepted") for d in days],
        "interactions": [_total(by_day.get(d, []), "interactions")
                         for d in days],
    }


def daily_inline_rate(activity_rows: list[dict], days: list[str]) -> dict:
    """Inline completion acceptance rate per day, as a percentage.

    Inline completion only, for the reason given in telemetry.py. A day below
    the minimum sample has no value."""
    by_day = _rows_by_day(_rows_in_mode(activity_rows, INLINE_COMPLETION_MODE))
    rates = []
    for day in days:
        rows = by_day.get(day, [])
        rate = _rate(_total(rows, "accepted"), _total(rows, "suggested"))
        rates.append(None if rate is None else round(rate * 100, 1))
    return {**_day_axis(days), "rates": rates}


def daily_people(user_rows: list[dict], days: list[str]) -> dict:
    """Distinct active people per day, and which days are Saturday or Sunday."""
    active = _rows_by_day([row for row in user_rows if is_active(row)])
    return {
        **_day_axis(days),
        "people": [len({row["user_login"] for row in active.get(d, [])})
                   for d in days],
        "weekend": [date.fromisoformat(d).weekday() >= 5 for d in days],
    }


def daily_lines(user_rows: list[dict], days: list[str]) -> dict:
    """Lines suggested and lines applied per day.

    Two separate counts, not a part and a whole: agent edits add lines
    without reporting them as suggested (see telemetry.py)."""
    by_day = _rows_by_day(user_rows)
    return {
        **_day_axis(days),
        "lines_suggested": [_total(by_day.get(d, []), "lines_suggested_added")
                            for d in days],
        "lines_added": [_total(by_day.get(d, []), "lines_added")
                        for d in days],
    }


def org_telemetry_view(source, month: str | None) -> dict:
    """Everything the org telemetry admin page shows for one month.

    `month` comes from the query string. It is only ever matched against the
    months the data holds, never parsed, so an unknown value falls back to
    the latest month.
    """
    if not source.telemetry_available():
        return {"available": False}
    months = source.org_telemetry_months()
    if not months:
        return {"available": True, "has_data": False}
    selected = _resolve_label(month, months)
    start_day, end_day = month_bounds(selected)
    user_rows = source.org_telemetry_user_rows(start_day, end_day)
    activity_rows = source.org_telemetry_activity_rows(start_day, end_day)
    if not user_rows:
        return {"available": True, "has_data": False}
    days = month_days(user_rows)
    return {
        "available": True,
        "has_data": True,
        "months": [{"value": m, "text": wpu.format_month_label(m)}
                   for m in months],
        "month": selected,
        "month_label": wpu.format_month_label(selected),
        "tiles": tiles(user_rows, activity_rows),
        "capability_share": capability_share(user_rows, days),
        "daily_activity": daily_activity(user_rows, days),
        "daily_inline_rate": daily_inline_rate(activity_rows, days),
        "daily_people": daily_people(user_rows, days),
        "daily_lines": daily_lines(user_rows, days),
    }
