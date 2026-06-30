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

    def model_rows(self) -> list[dict]:
        return self._cached("model_rows", self._inner.model_rows)

    def user_rows(self) -> list[dict]:
        return self._cached("user_rows", self._inner.user_rows)
