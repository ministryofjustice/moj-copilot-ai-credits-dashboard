"""S3-backed reports source — the same parquet tree as local, read from S3.

Reads `credits_by_model/` and `credits_by_user/` (Hive-partitioned by `day`) from
an S3 bucket via pyarrow's bundled S3 support (no s3fs). Selected when
REPORTS_SOURCE=s3.

Config (env):
* REPORTS_S3_BUCKET  - bucket name (required). Injected by Helm from the
                       namespace secret via secretKeyRef.
* REPORTS_S3_PREFIX  - key prefix the two table folders live under (default "").
* AWS_DEFAULT_REGION - region for the S3 filesystem (default "eu-west-2").

Credentials are resolved by the default AWS chain (IRSA / the pod's service
account role) - no static keys are read or stored here.
"""

from __future__ import annotations

import os

import pyarrow.dataset as ds
import pyarrow.fs as pafs

from app.main.services.reports_source import (
    DAY, ReportsSource, read_model_rows, read_user_rows)


class S3ReportsSource(ReportsSource):
    def __init__(self, bucket=None, prefix=None, region=None, filesystem=None) -> None:
        self.bucket = bucket or os.getenv("REPORTS_S3_BUCKET")
        if not self.bucket:
            raise ValueError("REPORTS_S3_BUCKET is required when REPORTS_SOURCE=s3")
        self.prefix = (prefix or os.getenv("REPORTS_S3_PREFIX") or "").strip("/")
        region = region or os.getenv("AWS_DEFAULT_REGION") or "eu-west-2"
        self._fs = filesystem if filesystem is not None else pafs.S3FileSystem(
            region=region)

    def _path(self, table: str) -> str:
        # No s3:// scheme when passing an explicit filesystem= to ds.dataset.
        base = "/".join(p for p in (self.bucket, self.prefix) if p)
        return f"{base}/{table}"

    def _dataset(self, table: str):
        return ds.dataset(self._path(table), filesystem=self._fs,
                          format="parquet", partitioning=DAY)

    def model_rows(self) -> list[dict]:
        return read_model_rows(self._dataset("credits_by_model"))

    def user_rows(self) -> list[dict]:
        return read_user_rows(self._dataset("credits_by_user"))
