"""Tests for CachingReportsSource — TTL memoisation in front of any backend.

Uses a call-counting fake source and an injectable clock (the project already
injects fakes/clocks rather than patching), so no real time or S3 is touched.
"""

from app.main.services.caching_reports_source import CachingReportsSource
from app.main.services.reports_source import ReportsSource


class FakeClock:  # pylint: disable=too-few-public-methods
    def __init__(self, now: float = 0.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


class CountingSource(ReportsSource):
    """Records how many times each method runs and returns marker payloads."""

    def __init__(self):
        self.model_calls = 0
        self.user_calls = 0

    def model_rows(self) -> list[dict]:
        self.model_calls += 1
        return [{"day": "2026-06-01", "model": "Opus", "model_family": "Opus",
                 "routed": False, "credits": float(self.model_calls)}]

    def user_rows(self) -> list[dict]:
        self.user_calls += 1
        return [{"day": "2026-06-01", "user_login": "a",
                 "credits": float(self.user_calls)}]


def _caching(inner, ttl=300.0, clock=None):
    return CachingReportsSource(inner, ttl_seconds=ttl, time_fn=clock or FakeClock())


def test_model_rows_calls_inner_once_within_ttl():
    inner = CountingSource()
    src = _caching(inner)
    first = src.model_rows()
    second = src.model_rows()
    assert inner.model_calls == 1
    assert first == second
    assert first[0]["credits"] == 1.0


def test_user_rows_calls_inner_once_within_ttl():
    inner = CountingSource()
    src = _caching(inner)
    assert src.user_rows()[0]["credits"] == 1.0
    assert src.user_rows()[0]["credits"] == 1.0
    assert inner.user_calls == 1


def test_model_and_user_cached_independently():
    inner = CountingSource()
    src = _caching(inner)
    src.model_rows()
    src.user_rows()
    assert inner.model_calls == 1
    assert inner.user_calls == 1


def test_cache_expires_after_ttl():
    inner = CountingSource()
    clock = FakeClock(now=1000.0)
    src = _caching(inner, ttl=300.0, clock=clock)
    src.model_rows()
    clock.now = 1000.0 + 299.0  # still inside the window
    src.model_rows()
    assert inner.model_calls == 1
    clock.now = 1000.0 + 301.0  # past the TTL
    assert src.model_rows()[0]["credits"] == 2.0
    assert inner.model_calls == 2


def test_ttl_zero_disables_caching():
    inner = CountingSource()
    src = _caching(inner, ttl=0.0)
    src.model_rows()
    src.model_rows()
    assert inner.model_calls == 2


def test_is_a_reports_source():
    assert isinstance(_caching(CountingSource()), ReportsSource)


class CountingTelemetrySource(ReportsSource):
    """Records the arguments of every telemetry call and echoes them back,
    so a cache that ignores an argument produces a visibly wrong answer."""

    def __init__(self):
        self.user_calls = []
        self.activity_calls = []

    def model_rows(self) -> list[dict]:
        return []

    def user_rows(self) -> list[dict]:
        return []

    def telemetry_available(self) -> bool:
        return True

    def telemetry_user_rows(self, login, start_day, end_day):
        self.user_calls.append((login, start_day, end_day))
        return [{"day": start_day, "login": login}]

    def telemetry_activity_rows(self, login, start_day, end_day):
        self.activity_calls.append((login, start_day, end_day))
        return [{"day": start_day, "login": login}]


def test_default_source_reports_no_telemetry():
    """A backend that knows nothing about telemetry must not claim to have it."""
    inner = CountingSource()
    assert inner.telemetry_available() is False
    assert inner.telemetry_user_rows("alice", "2026-08-01", "2026-08-31") == []
    assert inner.telemetry_activity_rows("alice", "2026-08-01", "2026-08-31") == []


def test_telemetry_availability_passes_through():
    src = _caching(CountingTelemetrySource())
    assert src.telemetry_available() is True


def test_telemetry_user_rows_cached_within_ttl():
    inner = CountingTelemetrySource()
    src = _caching(inner)
    src.telemetry_user_rows("alice", "2026-08-01", "2026-08-31")
    src.telemetry_user_rows("alice", "2026-08-01", "2026-08-31")
    assert len(inner.user_calls) == 1


def test_telemetry_user_rows_not_shared_between_people():
    """The bug this prevents: bob receiving alice's telemetry from the cache."""
    inner = CountingTelemetrySource()
    src = _caching(inner)
    alice = src.telemetry_user_rows("alice", "2026-08-01", "2026-08-31")
    bob = src.telemetry_user_rows("bob", "2026-08-01", "2026-08-31")
    assert alice[0]["login"] == "alice"
    assert bob[0]["login"] == "bob"
    assert len(inner.user_calls) == 2


def test_telemetry_user_rows_not_shared_between_months():
    inner = CountingTelemetrySource()
    src = _caching(inner)
    august = src.telemetry_user_rows("alice", "2026-08-01", "2026-08-31")
    july = src.telemetry_user_rows("alice", "2026-07-01", "2026-07-31")
    assert august[0]["day"] == "2026-08-01"
    assert july[0]["day"] == "2026-07-01"
    assert len(inner.user_calls) == 2


def test_telemetry_activity_rows_not_shared_between_people():
    inner = CountingTelemetrySource()
    src = _caching(inner)
    assert src.telemetry_activity_rows(
        "alice", "2026-08-01", "2026-08-31")[0]["login"] == "alice"
    assert src.telemetry_activity_rows(
        "bob", "2026-08-01", "2026-08-31")[0]["login"] == "bob"
    assert len(inner.activity_calls) == 2
