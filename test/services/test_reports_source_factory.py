"""Tests for get_reports_source() — backend selection and cache composition."""

import pytest

from app.main.services import reports_source as rs
from app.main.services.caching_reports_source import CachingReportsSource
from app.main.services.db_reports_source import DbReportsSource
from app.main.services.reports_source import LocalFsReportsSource, get_reports_source


def test_default_is_local_wrapped_in_cache(monkeypatch):
    monkeypatch.delenv("REPORTS_SOURCE", raising=False)
    monkeypatch.delenv("REPORTS_CACHE_TTL", raising=False)
    src = get_reports_source()
    assert isinstance(src, CachingReportsSource)
    assert isinstance(src._inner, LocalFsReportsSource)  # pylint: disable=protected-access


def test_cache_ttl_zero_returns_bare_source(monkeypatch):
    monkeypatch.setenv("REPORTS_SOURCE", "local")
    monkeypatch.setenv("REPORTS_CACHE_TTL", "0")
    src = get_reports_source()
    assert isinstance(src, LocalFsReportsSource)


def test_custom_ttl_passed_through(monkeypatch):
    monkeypatch.setenv("REPORTS_SOURCE", "local")
    monkeypatch.setenv("REPORTS_CACHE_TTL", "42")
    src = get_reports_source()
    assert isinstance(src, CachingReportsSource)
    assert src._ttl == 42.0  # pylint: disable=protected-access


def test_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("REPORTS_SOURCE", "nope")
    with pytest.raises(ValueError, match="Unknown REPORTS_SOURCE"):
        get_reports_source()


def test_s3_backend_removed(monkeypatch):
    monkeypatch.setenv("REPORTS_SOURCE", "s3")
    with pytest.raises(ValueError, match="Unknown REPORTS_SOURCE"):
        get_reports_source()


class _CountingSource(LocalFsReportsSource):
    """Counts how many times the underlying data is actually fetched."""

    def __init__(self):
        super().__init__("reports")
        self.fetches = 0

    def user_rows(self):
        self.fetches += 1
        return [{"day": "2026-06-01", "user_login": "a", "credits": 1.0}]


def test_cached_source_is_reused_across_calls(monkeypatch):
    """Regression: the caching source used to be rebuilt on every call, so its
    cache was discarded before it could ever be hit."""
    monkeypatch.setenv("REPORTS_SOURCE", "local")
    monkeypatch.setenv("REPORTS_CACHE_TTL", "300")
    assert get_reports_source() is get_reports_source()


def test_cache_survives_between_calls(monkeypatch):
    """Two separate get_reports_source() calls (i.e. two requests) must share one
    warm cache and hit the backend only once."""
    monkeypatch.setenv("REPORTS_SOURCE", "local")
    monkeypatch.setenv("REPORTS_CACHE_TTL", "300")
    inner = _CountingSource()
    monkeypatch.setattr(rs, "_build_source", lambda: inner)

    get_reports_source().user_rows()
    get_reports_source().user_rows()

    assert inner.fetches == 1


def test_caching_disabled_is_not_memoised(monkeypatch):
    """With the cache off, every call rebuilds — local dev keeps seeing file edits."""
    monkeypatch.setenv("REPORTS_SOURCE", "local")
    monkeypatch.setenv("REPORTS_CACHE_TTL", "0")
    assert get_reports_source() is not get_reports_source()


def test_db_backend_builds_db_source(monkeypatch):
    monkeypatch.setenv("REPORTS_SOURCE", "db")
    monkeypatch.setenv("REPORTS_CACHE_TTL", "0")  # bare source, easier to assert
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    monkeypatch.setenv("ATHENA_DATABASE", "db")
    monkeypatch.setenv("ATHENA_TABLE_MODELS", "cbm")
    monkeypatch.setenv("ATHENA_TABLE_USERS", "cbu")
    monkeypatch.setenv("ATHENA_OUTPUT_LOCATION", "s3://staging/")
    src = get_reports_source()
    assert isinstance(src, DbReportsSource)
