"""Shared pytest fixtures for the test suite.

Provides a single in-memory `ReportsSource` stub and a user-row factory so
individual test modules don't each redefine them (avoids duplicate-code) and
don't shadow the `credits` builtin.

The stub serves the two-method contract: `model_rows()` (org per-model) and
`user_rows()` ({day, user_login, credits}). `user_rows` is the first positional
arg because most views (pooled/weekly/my-usage) only need per-user data.
"""

import os

import pytest

from app.main.services.reports_source import ReportsSource

# Disable Auth0 for the whole test session so auth-protected routes are
# reachable without a live tenant. `app_config` reads this when create_app
# first runs (after collection), so setting it here is early enough.
os.environ.setdefault("AUTH_DISABLED", "true")


class _FakeSource(ReportsSource):
    def __init__(self, user_rows=None, model_rows=None):
        self._user_rows = list(user_rows or [])
        self._model_rows = list(model_rows or [])

    def model_rows(self):
        return self._model_rows

    def user_rows(self):
        return self._user_rows


@pytest.fixture
def fake_source():
    """Return a factory: (user_rows, model_rows=...) -> ReportsSource."""
    return _FakeSource


def _build_record(day, user, amount):
    """One per-user daily row: {day, user_login, credits}."""
    return {"day": day, "user_login": user, "credits": amount}


@pytest.fixture
def make_record():
    """Return a factory building one per-user daily row."""
    return _build_record


@pytest.fixture
def week_records():
    """Four user rows inside ISO week 2026-W23 / month 2026-06."""
    return [
        _build_record("2026-06-01", "a", 2000.0),
        _build_record("2026-06-02", "b", 50.0),
        _build_record("2026-06-03", "c", 30.0),
        _build_record("2026-06-04", "d", 20.0),
    ]
