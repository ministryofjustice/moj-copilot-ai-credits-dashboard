"""Tests for get_reports_source() — backend selection and cache composition."""

import pytest

from app.main.services.caching_reports_source import CachingReportsSource
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
