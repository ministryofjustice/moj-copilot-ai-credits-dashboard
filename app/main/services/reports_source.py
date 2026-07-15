"""Where AI-credit usage data comes from.

`ReportsSource` is the seam between the dashboard and its data. The data is the
two-table parquet dataset (`credits_by_model` + `credits_by_user`, Hive-partitioned
by `day`). Every backend returns plain row-lists that mirror the parquet 1:1:

* model_rows() -> [{day, model, model_family, routed, credits}, ...] across all days
                  (org-level per-model split; `routed` is True for `Auto:`-prefixed models).
* user_rows()  -> [{day, user_login, credits}, ...] across all days
                  (per-user daily totals; NO per-model breakdown exists in this data).

`day` is the partition column: it lives in the directory path (`day=YYYY-MM-DD/`),
not inside the file. The local source reads it back as a real date via the `DAY`
spec below; all backends normalise it to an ISO `YYYY-MM-DD` string in the
returned rows.

The local source reads `reports/` on disk; `DbReportsSource` reads the same data
from Athena (see db_reports_source.py).
"""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod

import pyarrow as pa
import pyarrow.dataset as ds

# Partition spec so `day=YYYY-MM-DD/` parses to a real date32 (not a string).
DAY = ds.partitioning(pa.schema([("day", pa.date32())]), flavor="hive")


def _iso(day) -> str:
    return day.isoformat() if hasattr(day, "isoformat") else str(day)


def model_rows_from_table(table) -> list[dict]:
    """Arrow table (model/model_family/routed/ai_credits_used/day) -> model rows."""
    c = table.to_pydict()
    return [
        {"day": _iso(d), "model": m, "model_family": mf,
         "routed": bool(r), "credits": float(v)}
        for d, m, mf, r, v in zip(c["day"], c["model"], c["model_family"],
                                  c["routed"], c["ai_credits_used"])
    ]


def user_rows_from_table(table) -> list[dict]:
    """Arrow table (user_login/ai_credits_used/day) -> user rows."""
    c = table.to_pydict()
    return [
        {"day": _iso(d), "user_login": u, "credits": float(v)}
        for d, u, v in zip(c["day"], c["user_login"], c["ai_credits_used"])
    ]


def read_model_rows(dataset) -> list[dict]:
    """Read a `credits_by_model` pyarrow dataset into model rows."""
    return model_rows_from_table(dataset.to_table(
        columns=["model", "model_family", "routed", "ai_credits_used", "day"]))


def read_user_rows(dataset) -> list[dict]:
    """Read a `credits_by_user` pyarrow dataset into user rows."""
    return user_rows_from_table(dataset.to_table(
        columns=["user_login", "ai_credits_used", "day"]))


class ReportsSource(ABC):
    """Read-only access to captured AI-credit usage, independent of backend."""

    @abstractmethod
    def model_rows(self) -> list[dict]:
        """[{day, model, model_family, routed, credits}, ...] across all days."""

    @abstractmethod
    def user_rows(self) -> list[dict]:
        """[{day, user_login, credits}, ...] across all days."""


class LocalFsReportsSource(ReportsSource):
    """Reads the on-disk `reports/credits_by_{model,user}/day=.../` parquet tree.

    This is the dev/default source. `reports_dir` is the root that contains the
    two table folders (default "reports", overridable via the REPORTS_DIR env var).
    """

    def __init__(self, reports_dir: str = "reports") -> None:
        self.reports_dir = reports_dir

    def _dataset(self, table: str):
        return ds.dataset(os.path.join(self.reports_dir, table),
                          format="parquet", partitioning=DAY)

    def model_rows(self) -> list[dict]:
        return read_model_rows(self._dataset("credits_by_model"))

    def user_rows(self) -> list[dict]:
        return read_user_rows(self._dataset("credits_by_user"))


def _build_source() -> ReportsSource:
    """Pick the raw backend from config. REPORTS_SOURCE = local (default)|db."""
    # pylint: disable=import-outside-toplevel
    backend = (os.getenv("REPORTS_SOURCE") or "local").lower()
    if backend == "local":
        return LocalFsReportsSource(os.getenv("REPORTS_DIR") or "reports")
    if backend == "db":
        from app.main.services.db_reports_source import DbReportsSource

        return DbReportsSource()
    raise ValueError(f"Unknown REPORTS_SOURCE: {backend!r} (expected local|db)")


# The caching source holds its entries in instance state, so it only caches
# anything if the *same instance* is reused across requests. Hence one per
# process, built on first use and kept for the process's life.
_LOCK = threading.Lock()
_SOURCE: ReportsSource | None = None


def reset_reports_source() -> None:
    """Drop the memoised source so the next call rebuilds it from the env.

    Only needed by tests (the env vars are read once, at build time).
    """
    global _SOURCE  # pylint: disable=global-statement
    with _LOCK:
        _SOURCE = None


def get_reports_source() -> ReportsSource:
    """The configured backend, wrapped in a TTL cache unless disabled.

    The data changes ~once a day but each request otherwise re-fetches it, so by
    default the source is memoised for REPORTS_CACHE_TTL seconds (default 300). Set
    REPORTS_CACHE_TTL=0 to disable caching (e.g. local dev where you want to see
    file edits at once).

    The wrapped source is built once per process and reused, so the cache actually
    survives between requests. With caching disabled the bare source is rebuilt each
    call, which keeps local dev reading the files fresh every time.
    """
    # pylint: disable=import-outside-toplevel,global-statement
    global _SOURCE
    if _SOURCE is not None:
        return _SOURCE
    with _LOCK:
        if _SOURCE is not None:  # another thread built it while we waited
            return _SOURCE
        source = _build_source()
        ttl = float(os.getenv("REPORTS_CACHE_TTL") or 300)
        if ttl <= 0:
            return source  # caching off: don't memoise, stay fresh
        from app.main.services.caching_reports_source import CachingReportsSource

        _SOURCE = CachingReportsSource(source, ttl_seconds=ttl)
        return _SOURCE
