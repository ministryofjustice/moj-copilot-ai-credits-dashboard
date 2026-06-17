"""Where AI-credit usage data comes from.

`ReportsSource` is the seam between the dashboard and its data. Today the only
implementation reads the local `reports/` tree (the same files the Streamlit app
used). Soon the data will come from S3, and later from a database — those land as
`S3ReportsSource` / `DbReportsSource` (see s3_reports_source.py,
db_reports_source.py) implementing the same three methods, with nothing in the
aggregation logic, routes, or templates needing to change.

Contract — every source returns plain JSON-shaped Python:

* daily_docs()        -> {day: raw ai-credit-usage doc}
                         doc has "usageItems" and an "organization"/"enterprise".
* per_user_docs(day)  -> {login: [usageItem, ...]} for that day.
* weekly_records()    -> [{day, user, credits, usd, per_model}, ...] across all
                         captured days (the shape `weekly_per_user.rollup_weekly`
                         expects).
"""

from __future__ import annotations

import glob
import json
import os
from abc import ABC, abstractmethod

from app.main.services import weekly_per_user as wpu


class ReportsSource(ABC):
    """Read-only access to captured AI-credit usage, independent of backend."""

    @abstractmethod
    def daily_docs(self) -> dict[str, dict]:
        """Map 'YYYY-MM-DD' -> raw org/enterprise ai-credit-usage document."""

    @abstractmethod
    def per_user_docs(self, day: str) -> dict[str, list]:
        """Map login -> that user's usageItems for a single day ({} if none)."""

    @abstractmethod
    def weekly_records(self) -> list[dict]:
        """Per-(day, user) usage records across every captured day."""


class LocalFsReportsSource(ReportsSource):
    """Reads the on-disk `reports/<date>/billing/...` tree.

    This is the dev/default source. `reports_dir` is the root that contains the
    per-day folders (default "reports", overridable via the REPORTS_DIR env var).
    """

    def __init__(self, reports_dir: str = "reports") -> None:
        self.reports_dir = reports_dir

    def _day_from_path(self, path: str) -> str:
        # <reports_dir>/2026-06-04/billing/ai-credit-usage.json -> 2026-06-04
        rel = os.path.relpath(path, self.reports_dir)
        return rel.replace("\\", "/").split("/")[0]

    def daily_docs(self) -> dict[str, dict]:
        pattern = os.path.join(self.reports_dir, "*", "billing", "ai-credit-usage.json")
        docs: dict[str, dict] = {}
        for path in sorted(glob.glob(pattern)):
            with open(path, encoding="utf-8") as f:
                docs[self._day_from_path(path)] = json.load(f)
        return dict(sorted(docs.items()))

    def per_user_docs(self, day: str) -> dict[str, list]:
        pattern = os.path.join(self.reports_dir, day, "billing", "per-user", "*.json")
        out: dict[str, list] = {}
        for path in sorted(glob.glob(pattern)):
            login = os.path.splitext(os.path.basename(path))[0]
            with open(path, encoding="utf-8") as f:
                out[login] = json.load(f).get("usageItems", [])
        return out

    def weekly_records(self) -> list[dict]:
        pattern = os.path.join(
            self.reports_dir, "*", "billing", "per-user", "*.json"
        )
        return wpu.load_weekly_records(pattern)


def get_reports_source() -> ReportsSource:
    """Pick the source from config. REPORTS_SOURCE = local (default) | s3 | db."""
    # pylint: disable=import-outside-toplevel
    backend = (os.getenv("REPORTS_SOURCE") or "local").lower()
    if backend == "local":
        return LocalFsReportsSource(os.getenv("REPORTS_DIR") or "reports")
    if backend == "s3":
        from app.main.services.s3_reports_source import S3ReportsSource

        return S3ReportsSource()
    if backend == "db":
        from app.main.services.db_reports_source import DbReportsSource

        return DbReportsSource()
    raise ValueError(f"Unknown REPORTS_SOURCE: {backend!r} (expected local|s3|db)")
