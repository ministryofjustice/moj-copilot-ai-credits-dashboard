"""Database-backed reports source. Stub — to be implemented later.

Implement the three `ReportsSource` methods by querying the usage tables and
returning the same documented shapes (daily docs, per-user docs, weekly records).
Nothing else in the app should need to change.
"""

from __future__ import annotations

from app.main.services.reports_source import ReportsSource


class DbReportsSource(ReportsSource):
    def __init__(self) -> None:
        raise NotImplementedError("DbReportsSource is not implemented yet.")

    def daily_docs(self) -> dict[str, dict]:
        raise NotImplementedError

    def per_user_docs(self, day: str) -> dict[str, list]:
        raise NotImplementedError

    def weekly_records(self) -> list[dict]:
        raise NotImplementedError
