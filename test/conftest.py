"""Shared pytest fixtures for the test suite.

Provides a single in-memory `ReportsSource` stub and a report-record factory so
individual test modules don't each redefine them (avoids duplicate-code) and
don't shadow the `credits` builtin.
"""

import pytest

from app.main.services.reports_source import ReportsSource


class _FakeSource(ReportsSource):
    def __init__(self, records):
        self._records = records

    def daily_docs(self):
        return {}

    def per_user_docs(self, day):
        return {}

    def weekly_records(self):
        return self._records


@pytest.fixture
def fake_source():
    """Return a factory: records -> ReportsSource serving those weekly records."""
    return _FakeSource


def _build_record(day, user, amount):
    return {
        "day": day,
        "user": user,
        "credits": amount,
        "usd": amount / 100.0,
        "per_model": {"gpt": amount},
    }


@pytest.fixture
def make_record():
    """Return a factory building one weekly report record."""
    return _build_record


@pytest.fixture
def week_records():
    """Four weekly records inside ISO week 2026-W23 / month 2026-06."""
    return [
        _build_record("2026-06-01", "a", 2000.0),
        _build_record("2026-06-02", "b", 50.0),
        _build_record("2026-06-03", "c", 30.0),
        _build_record("2026-06-04", "d", 20.0),
    ]
