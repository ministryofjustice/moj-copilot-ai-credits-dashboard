"""TTL-caching wrapper around any ReportsSource.

The usage data changes about once a day, but the S3 backend re-fetches it on
every request (one GetObject per file across thousands of per-user JSONs ~= 15s).
This wraps any source and memoises its three methods for `ttl_seconds`, so repeat
requests are served from memory. It is itself a `ReportsSource`, so the factory
can compose it transparently and routes/views are untouched.

The cache is per-process (per gunicorn worker); each worker warms independently.
The clock is injectable (`time_fn`, default `time.monotonic`) so TTL expiry is
testable without sleeping or freezing wall-clock time. `ttl_seconds <= 0`
disables caching entirely (every call hits the inner source).
"""

from __future__ import annotations

import threading
import time

from app.main.services.reports_source import ReportsSource


class CachingReportsSource(ReportsSource):
    def __init__(self, inner: ReportsSource, ttl_seconds: float = 300.0,
                 time_fn=time.monotonic) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._now = time_fn
        self._lock = threading.Lock()
        self._cache: dict[object, tuple[float, object]] = {}

    def _cached(self, key, produce):
        if self._ttl <= 0:
            return produce()
        now = self._now()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and now - entry[0] < self._ttl:
                return entry[1]
        value = produce()
        with self._lock:
            self._cache[key] = (now, value)
        return value

    def daily_docs(self) -> dict[str, dict]:
        return self._cached("daily_docs", self._inner.daily_docs)

    def per_user_docs(self, day: str) -> dict[str, list]:
        return self._cached(("per_user_docs", day),
                            lambda: self._inner.per_user_docs(day))

    def weekly_records(self) -> list[dict]:
        return self._cached("weekly_records", self._inner.weekly_records)
