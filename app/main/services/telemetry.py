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

TOP_LANGUAGE_COUNT = 8


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
