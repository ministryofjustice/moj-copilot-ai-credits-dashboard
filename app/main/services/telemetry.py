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
  lines-kept ratio over everything exceeds 100 per cent. Both rates this
  module computes cover inline completion alone, and both are dropped when
  the numerator exceeds the denominator or the sample is under MIN_FOR_RATE.
* Acceptance is not reported per mode. Agent features apply code without a
  discrete accept step, so their acceptance counts are near zero and a rate
  would misrepresent people who work mainly through agents. Inline completion
  is the exception, reported on its own by `inline_completion`, because there
  the person either takes the suggestion or does not.
"""

from __future__ import annotations

import calendar

VOLUME_FIELDS = ("interactions", "suggested", "accepted",
                 "lines_added", "lines_deleted")

# Counts summed per group (per mode, per language) and for inline completion.
GROUPED_FIELDS = ("suggested", "accepted", "lines_added",
                  "lines_suggested_added")

# The two mode names this module singles out. The pipeline derives `mode` from
# `feature`; these are two of the six values it produces.
INLINE_COMPLETION_MODE = "Inline completion"
AGENT_MODE = "Agent mode"

# Below this many events, a percentage says more about the small sample than
# about the person, so none is shown.
MIN_FOR_RATE = 20


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
    """Sum every count in GROUPED_FIELDS per group, skipping nulls and any row
    whose key is None."""
    totals: dict = {}
    for row in rows:
        key = key_of(row)
        if key is None:
            continue
        entry = totals.setdefault(key, {f: 0 for f in GROUPED_FIELDS})
        for field in GROUPED_FIELDS:
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


def _rate(part: int, whole: int) -> float | None:
    """`part / whole`, or None when that fraction would not be a fact.

    Two things make it not a fact: too few events to measure, and a part larger
    than its whole. The second happens in the real data - GitHub has been seen
    reporting more acceptances than offers, and it leaves agent edits out of
    the suggested-lines column while counting them in lines added.
    """
    if whole < MIN_FOR_RATE or part > whole:
        return None
    return part / whole


def _rows_in_mode(activity_rows: list[dict], mode: str) -> list[dict]:
    return [row for row in activity_rows if row.get("mode") == mode]


def inline_completion(activity_rows: list[dict]) -> dict:
    """Month totals and two rates for inline completion alone.

    Inline completion is the only surface where offered and accepted are a
    matched pair, because the person either takes the suggestion or does not.
    Every other surface either applies code without an accept step or records
    almost no acceptances, so a rate across all of them understates everyone.
    """
    rows = _rows_in_mode(activity_rows, INLINE_COMPLETION_MODE)
    figures = {field: _total(rows, field) for field in GROUPED_FIELDS}
    figures["acceptance_rate"] = _rate(figures["accepted"], figures["suggested"])
    figures["lines_kept_rate"] = _rate(figures["lines_added"],
                                       figures["lines_suggested_added"])
    return figures


def agent_lines_added(activity_rows: list[dict]) -> int:
    """Lines agent edits wrote into files. Reported on its own because these
    lines are never counted as accepted suggestions, so a page that showed only
    acceptances would describe an agent user as having done nothing."""
    return _total(_rows_in_mode(activity_rows, AGENT_MODE), "lines_added")


def headline(inline: dict, modes: list[dict], languages: list[dict],
             agent_lines: int) -> dict:
    """The parts of the one-sentence summary, as values rather than text.

    The sentence is written in the template. Keeping the wording out of Python
    means the phrasing can change without touching a tested calculation, and a
    part that was never recorded arrives as None so the template can leave that
    clause out rather than print a placeholder.
    """
    return {
        "acceptance_rate": inline["acceptance_rate"],
        "inline_suggested": inline["suggested"],
        "top_language": languages[0]["language"] if languages else None,
        "top_mode": modes[0]["mode"] if modes else None,
        "agent_lines_added": agent_lines,
    }


# GitHub does not standardise the language strings it reports: the August 2026
# data carries 141 distinct values, including both `c#` and `csharp`, all four
# of `shell`/`shellscript`/`bash`/`sh`, and all four of
# `terraform`/`hcl`/`tf`/`terraform-vars`. This folds the observed aliases
# together for display only. The raw value stays in the row and is never
# rewritten, so a wrong entry here can be corrected without reprocessing data.
# An unlisted value is shown as it arrived.
LANGUAGE_DISPLAY = {
    "ts": "TypeScript", "typescript": "TypeScript", "tsx": "TypeScript",
    "js": "JavaScript", "javascript": "JavaScript", "jsx": "JavaScript",
    "py": "Python", "python": "Python",
    "terraform": "Terraform", "hcl": "Terraform", "tf": "Terraform",
    "terraform-vars": "Terraform",
    "md": "Markdown", "markdown": "Markdown",
    "yml": "YAML", "yaml": "YAML",
    "sh": "Shell", "bash": "Shell", "zsh": "Shell", "shell": "Shell",
    "shellscript": "Shell",
    "powershell": "PowerShell",
    "rb": "Ruby", "ruby": "Ruby",
    "rs": "Rust", "rust": "Rust",
    "cs": "C#", "csharp": "C#", "c#": "C#",
    "cpp": "C++", "c": "C",
    "go": "Go", "golang": "Go",
    "r": "R",
    "java": "Java", "kotlin": "Kotlin", "swift": "Swift", "php": "PHP",
    "vb": "Visual Basic",
    "razor": "Razor", "aspnetcorerazor": "Razor", "html+razor": "Razor",
    "jinja": "Jinja", "jinja-yaml": "Jinja", "jinja-sql": "Jinja",
    "njk": "Nunjucks", "nunjucks": "Nunjucks",
    "json": "JSON", "jsonc": "JSON", "xml": "XML", "html": "HTML",
    "css": "CSS", "scss": "SCSS",
    "sql": "SQL", "oracle-sql": "Oracle SQL",
    "dockerfile": "Dockerfile", "dockercompose": "Docker Compose",
    "makefile": "Makefile", "dotenv": "Dotenv", "csv": "CSV",
    "github-actions-workflow": "GitHub Actions workflow",
    "groovy": "Groovy", "gherkin": "Gherkin", "svelte": "Svelte",
    "ansible": "Ansible",
}

# Values GitHub reports in the language field that are not languages. In the
# August 2026 data `unknown` alone is the seventh largest value by lines added,
# so ranking these beside Python would misdescribe what the person wrote. They
# are excluded from the ranking and their lines reported separately.
NON_LANGUAGES = frozenset({
    "prompt", "instructions", "vscode", "others", "other", "unknown",
    "plaintext", "text", "none", "skill", "chatagent", "git-commit",
})

TOP_LANGUAGE_COUNT = 5


def display_language(raw: str | None) -> str | None:
    """The name to show for a raw language string, or None if it is not a
    language at all."""
    if raw is None:
        return None
    key = raw.strip().lower()
    if not key or key in NON_LANGUAGES:
        return None
    return LANGUAGE_DISPLAY.get(key, raw)


def top_languages(activity_rows: list[dict],
                  limit: int = TOP_LANGUAGE_COUNT) -> list[dict]:
    """The languages Copilot wrote most for this person, ranked by lines added.

    Anything past `limit` is combined into a single "Other" entry so the table
    stays readable and still adds up. Values that are not languages are left
    out entirely; see `unattributed_lines`.
    """
    totals = _grouped_totals(
        activity_rows, lambda row: display_language(row.get("language")))
    ranked = sorted(
        ({"language": name,
          "suggested": entry["suggested"],
          "lines_added": entry["lines_added"]}
         for name, entry in totals.items()),
        key=lambda lang: (-lang["lines_added"], lang["language"]),
    )
    head, tail = ranked[:limit], ranked[limit:]
    if tail:
        head.append({
            "language": "Other",
            "suggested": sum(lang["suggested"] for lang in tail),
            "lines_added": sum(lang["lines_added"] for lang in tail),
        })
    return head


def unattributed_lines(activity_rows: list[dict]) -> int:
    """Lines added under a value that is not a language, such as `unknown` or
    `prompt`. Reported so the language table's total is not silently short."""
    return sum(
        row["lines_added"] for row in activity_rows
        if row.get("lines_added") is not None
        and display_language(row.get("language")) is None
    )


def month_bounds(month: str) -> tuple[str, str]:
    """`YYYY-MM` -> the first and last calendar day of that month, inclusive."""
    year, month_number = (int(part) for part in month.split("-"))
    last = calendar.monthrange(year, month_number)[1]
    return f"{month}-01", f"{month}-{last:02d}"


def telemetry_view(source, login: str, month: str) -> dict | None:
    """Everything the personal page shows about one person's month, or None.

    None means the section does not render at all, for either of two reasons:
    the backend serves no telemetry (which is how the feature stays switched
    off outside development), or this person has no rows for this month.
    """
    if not source.telemetry_available():
        return None
    start_day, end_day = month_bounds(month)
    user_rows = source.telemetry_user_rows(login, start_day, end_day)
    activity_rows = source.telemetry_activity_rows(login, start_day, end_day)
    if not user_rows and not activity_rows:
        return None
    modes = mode_split(activity_rows)
    languages = top_languages(activity_rows)
    inline = inline_completion(activity_rows)
    agent_lines = agent_lines_added(activity_rows)
    return {
        "month": month,
        "volume": volume(user_rows),
        "review": review_activity(user_rows),
        "modes": modes,
        "languages": languages,
        "inline": inline,
        "agent_lines_added": agent_lines,
        "headline": headline(inline, modes, languages, agent_lines),
        "unattributed_lines_added": unattributed_lines(activity_rows),
    }
