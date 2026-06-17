import json

import pytest

from app.main.services.s3_reports_source import S3ReportsSource


class _Body:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class _Paginator:
    def __init__(self, store: dict):
        self._store = store

    def paginate(self, Bucket, Prefix):  # noqa: N803 (boto3 kwarg names)
        contents = [
            {"Key": k} for k in sorted(self._store) if k.startswith(Prefix)
        ]
        yield {"Contents": contents}


class FakeS3Client:
    """Minimal in-memory stand-in for a boto3 S3 client."""

    def __init__(self, objects: dict[str, dict]):
        self._store = {k: json.dumps(v).encode("utf-8") for k, v in objects.items()}

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return _Paginator(self._store)

    def get_object(self, Bucket, Key):  # noqa: N803
        return {"Body": _Body(self._store[Key])}


def _source(objects, prefix="reports"):
    return S3ReportsSource(
        bucket="test-bucket", prefix=prefix, client=FakeS3Client(objects)
    )


def test_daily_docs_keyed_by_date_sorted():
    src = _source({
        "reports/2026-06-02/billing/ai-credit-usage.json": {
            "enterprise": "MoJ", "usageItems": [{"model": "Opus"}]},
        "reports/2026-06-01/billing/ai-credit-usage.json": {
            "enterprise": "MoJ", "usageItems": []},
        "reports/2026-06-01/billing/per-user/alice.json": {"usageItems": []},
    })
    docs = src.daily_docs()
    assert list(docs) == ["2026-06-01", "2026-06-02"]
    assert docs["2026-06-02"]["usageItems"] == [{"model": "Opus"}]
