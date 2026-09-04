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


def test_cache_expires_at_the_end_of_the_window():
    inner = CountingSource()
    clock = FakeClock(now=1000.0)  # window 3 of 300s runs [900, 1200)
    src = _caching(inner, ttl=300.0, clock=clock)
    src.model_rows()
    clock.now = 1199.0  # still inside the same window
    src.model_rows()
    assert inner.model_calls == 1
    clock.now = 1201.0  # the window has rolled over
    assert src.model_rows()[0]["credits"] == 2.0
    assert inner.model_calls == 2


def test_window_boundaries_do_not_depend_on_when_the_cache_warmed():
    """Each running copy of the app caches separately, and they warm at whatever
    moment each first got a request. Their windows must still start and end at
    the same instants; otherwise one copy holds new data while another still
    holds the previous day's, and refreshing bounces between the two figures.
    """
    def refetch_instants(warmed_at: float) -> list[int]:
        inner = CountingSource()
        clock = FakeClock(now=warmed_at)
        src = _caching(inner, ttl=300.0, clock=clock)
        src.model_rows()  # this copy warms its cache here
        instants = []
        for tick in range(1500, 3000):
            clock.now = float(tick)
            before = inner.model_calls
            src.model_rows()
            if inner.model_calls != before:
                instants.append(tick)
        return instants

    assert refetch_instants(1000.0) == refetch_instants(1250.0)
    assert refetch_instants(1000.0) == [1500, 1800, 2100, 2400, 2700]


def test_ttl_zero_disables_caching():
    inner = CountingSource()
    src = _caching(inner, ttl=0.0)
    src.model_rows()
    src.model_rows()
    assert inner.model_calls == 2


def test_is_a_reports_source():
    assert isinstance(_caching(CountingSource()), ReportsSource)
