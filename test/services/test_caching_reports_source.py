"""Tests for CachingReportsSource — TTL memoisation in front of any backend.

Uses a call-counting fake source and an injectable clock (the project already
injects fakes/clocks rather than patching), so no real time or S3 is touched.
"""

from app.main.services.caching_reports_source import CachingReportsSource
from app.main.services.reports_source import ReportsSource


class FakeClock:
    def __init__(self, now: float = 0.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


class CountingSource(ReportsSource):
    """Records how many times each method runs and returns marker payloads."""

    def __init__(self):
        self.daily_calls = 0
        self.per_user_calls: list[str] = []
        self.weekly_calls = 0

    def daily_docs(self) -> dict[str, dict]:
        self.daily_calls += 1
        return {"2026-06-01": {"n": self.daily_calls}}

    def per_user_docs(self, day: str) -> dict[str, list]:
        self.per_user_calls.append(day)
        return {"alice": [{"day": day, "n": len(self.per_user_calls)}]}

    def weekly_records(self) -> list[dict]:
        self.weekly_calls += 1
        return [{"n": self.weekly_calls}]


def _caching(inner, ttl=300.0, clock=None):
    return CachingReportsSource(inner, ttl_seconds=ttl, time_fn=clock or FakeClock())


def test_daily_docs_calls_inner_once_within_ttl():
    inner = CountingSource()
    src = _caching(inner)
    first = src.daily_docs()
    second = src.daily_docs()
    assert inner.daily_calls == 1
    assert first == second == {"2026-06-01": {"n": 1}}


def test_weekly_records_calls_inner_once_within_ttl():
    inner = CountingSource()
    src = _caching(inner)
    assert src.weekly_records() == [{"n": 1}]
    assert src.weekly_records() == [{"n": 1}]
    assert inner.weekly_calls == 1


def test_per_user_docs_cached_per_day():
    inner = CountingSource()
    src = _caching(inner)
    src.per_user_docs("2026-06-01")
    src.per_user_docs("2026-06-01")
    src.per_user_docs("2026-06-02")
    assert inner.per_user_calls == ["2026-06-01", "2026-06-02"]


def test_cache_expires_after_ttl():
    inner = CountingSource()
    clock = FakeClock(now=1000.0)
    src = _caching(inner, ttl=300.0, clock=clock)
    src.daily_docs()
    clock.now = 1000.0 + 299.0  # still inside the window
    src.daily_docs()
    assert inner.daily_calls == 1
    clock.now = 1000.0 + 301.0  # past the TTL
    assert src.daily_docs() == {"2026-06-01": {"n": 2}}
    assert inner.daily_calls == 2


def test_ttl_zero_disables_caching():
    inner = CountingSource()
    src = _caching(inner, ttl=0.0)
    src.daily_docs()
    src.daily_docs()
    assert inner.daily_calls == 2


def test_is_a_reports_source():
    assert isinstance(_caching(CountingSource()), ReportsSource)
