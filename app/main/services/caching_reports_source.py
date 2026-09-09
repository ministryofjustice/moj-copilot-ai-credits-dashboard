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

The cache is per-process and production runs several replicas, so the caches must
expire together or a refresh gets an old figure from one replica and a new one
from the next. Time is therefore cut into fixed `ttl_seconds` windows counted
from the epoch, and an entry is valid only in the window it was fetched in: every
process computes the same window number and they roll over together.

`time_fn` must be a wall clock shared by all processes (`time.monotonic` counts
from a per-process origin, which is what put them out of step). `ttl_seconds <= 0`
disables caching entirely.
"""

from __future__ import annotations

import threading
import time
import os

from app.main.services.reports_source import ReportsSource


class CachingReportsSource(ReportsSource):
    def __init__(self, inner: ReportsSource, ttl_seconds: float = 300.0,
                 time_fn=time.time) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._now = time_fn
        self._lock = threading.Lock()
        self._cache: dict[object, tuple[int, object]] = {}
        self._pod_name = os.getenv("HOSTNAME", "unknown")

    def _cached(self, key, produce):
        if self._ttl <= 0:
            return produce()
        now = self._now()
        window = int(now // self._ttl)
        expires_at = (window + 1) * self._ttl
        seconds_remaining = expires_at - now
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and entry[0] == window:
                print(
                    "reports cache hit "
                    f"key={key} window={window} expires_at={expires_at} "
                    f"seconds_remaining={seconds_remaining:.3f} "
                    f"pod={self._pod_name}"
                )
                return entry[1]
        value = produce()
        with self._lock:
            self._cache[key] = (window, value)
        print(
            "reports cache refresh "
            f"key={key} window={window} expires_at={expires_at} "
            f"seconds_remaining={seconds_remaining:.3f} "
            f"pod={self._pod_name}"
        )
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
