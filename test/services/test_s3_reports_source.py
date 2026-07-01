"""S3ReportsSource tests.

The S3 read path is pure pyarrow `ds.dataset(..., filesystem=...)`; injecting a
`LocalFileSystem` over a tmp parquet tree exercises the exact same code (path
building + partition parsing) without touching real S3. `bucket` doubles as the
on-disk root because `_path` joins bucket/prefix/table.
"""

import pyarrow.fs as pafs
import pytest

from app.main.services.s3_reports_source import S3ReportsSource
from services.parquet_fixtures import write_model_partition, write_user_partition


def _source(tmp_path, prefix=""):
    return S3ReportsSource(bucket=str(tmp_path), prefix=prefix,
                           filesystem=pafs.LocalFileSystem())


def test_model_rows_over_injected_fs(tmp_path):
    write_model_partition(str(tmp_path), "2026-06-01",
                          [("Opus 4.6", "Opus", False, 9.0),
                           ("Auto: Haiku", "Haiku", True, 1.0)])
    rows = _source(tmp_path).model_rows()
    by_model = {r["model"]: r for r in rows}
    assert by_model["Opus 4.6"]["day"] == "2026-06-01"
    assert by_model["Opus 4.6"]["credits"] == 9.0
    assert by_model["Auto: Haiku"]["routed"] is True


def test_user_rows_over_injected_fs(tmp_path):
    write_user_partition(str(tmp_path), "2026-06-02", [("alice", 12.5)])
    rows = _source(tmp_path).user_rows()
    assert rows == [{"day": "2026-06-02", "user_login": "alice", "credits": 12.5}]


def test_custom_prefix_is_honoured(tmp_path):
    sub = tmp_path / "data"
    write_model_partition(str(sub), "2026-06-01", [("Opus", "Opus", False, 3.0)])
    rows = S3ReportsSource(bucket=str(tmp_path), prefix="data",
                           filesystem=pafs.LocalFileSystem()).model_rows()
    assert rows[0]["credits"] == 3.0


def test_missing_bucket_raises(monkeypatch):
    monkeypatch.delenv("REPORTS_S3_BUCKET", raising=False)
    with pytest.raises(ValueError, match="REPORTS_S3_BUCKET"):
        S3ReportsSource(filesystem=pafs.LocalFileSystem())
