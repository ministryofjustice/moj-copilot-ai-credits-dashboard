"""TTL-caching wrapper around any ReportsSource.

The usage data changes about once a day, but the backends otherwise re-fetch it
on every request. This wraps any source and memoises its two methods for
`ttl_seconds`, so repeat requests are served from memory. It is itself a
`ReportsSource`, so the factory can compose it transparently and routes/views
are untouched.

The two whole-table methods are keyed by name alone. The telemetry methods take
arguments, so they are keyed by name plus the username and both dates: without
that, the first person to load the page would have their telemetry served to
everyone else until the entry expired.

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

    def telemetry_available(self) -> bool:
        # Cheap and constant for the life of the process; not worth caching.
        return self._inner.telemetry_available()

    def telemetry_user_rows(self, login: str, start_day: str,
                            end_day: str) -> list[dict]:
        return self._cached(
            ("telemetry_user_rows", login, start_day, end_day),
            lambda: self._inner.telemetry_user_rows(login, start_day, end_day),
        )

    def telemetry_activity_rows(self, login: str, start_day: str,
                                end_day: str) -> list[dict]:
        return self._cached(
            ("telemetry_activity_rows", login, start_day, end_day),
            lambda: self._inner.telemetry_activity_rows(login, start_day, end_day),
        )
