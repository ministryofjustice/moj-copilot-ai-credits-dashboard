"""S3-backed reports source. Stub — to be implemented when data moves to S3.

Implement the three `ReportsSource` methods by listing/fetching the same
`reports/<date>/billing/...` objects from a bucket (boto3) and parsing the JSON
into the documented shapes. Nothing else in the app should need to change.
"""

from __future__ import annotations

from app.main.services.reports_source import ReportsSource


class S3ReportsSource(ReportsSource):
    def __init__(self) -> None:
        raise NotImplementedError("S3ReportsSource is not implemented yet.")

    def daily_docs(self) -> dict[str, dict]:
        raise NotImplementedError

    def per_user_docs(self, day: str) -> dict[str, list]:
        raise NotImplementedError

    def weekly_records(self) -> list[dict]:
        raise NotImplementedError
