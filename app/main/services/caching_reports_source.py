"""TTL-caching wrapper around any ReportsSource.

The usage data changes about once a day, but the backends otherwise re-fetch it
on every request. This wraps any source and memoises its two methods for
`ttl_seconds`, so repeat requests are served from memory. It is itself a
`ReportsSource`, so the factory can compose it transparently and routes/views
are untouched.

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

from app.main.services.reports_source import ReportsSource


class CachingReportsSource(ReportsSource):
    def __init__(self, inner: ReportsSource, ttl_seconds: float = 300.0,
                 time_fn=time.time) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._now = time_fn
        self._lock = threading.Lock()
        self._cache: dict[object, tuple[int, object]] = {}

    def _cached(self, key, produce):
        if self._ttl <= 0:
            return produce()
        window = int(self._now() // self._ttl)
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and entry[0] == window:
                return entry[1]
        value = produce()
        with self._lock:
            self._cache[key] = (window, value)
        return value

    def model_rows(self) -> list[dict]:
        return self._cached("model_rows", self._inner.model_rows)

    def user_rows(self) -> list[dict]:
        return self._cached("user_rows", self._inner.user_rows)
