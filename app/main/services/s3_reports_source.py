"""S3-backed reports source.

Reads the same `reports/<date>/billing/...` JSON tree that LocalFsReportsSource
reads on disk, but from an S3 bucket. Selected when REPORTS_SOURCE=s3.

Config (env):
* REPORTS_S3_BUCKET  - bucket name (required). Injected by Helm from the
                       namespace secret via secretKeyRef.
* REPORTS_S3_PREFIX  - key prefix the report tree lives under (default "reports").
* AWS_DEFAULT_REGION - region for the boto3 client (default "eu-west-2").

Credentials are resolved by boto3's default chain (IRSA / the pod's service
account role) - no static keys are read or stored here.
"""

from __future__ import annotations

import json
import os

from app.main.services import weekly_per_user as wpu
from app.main.services.reports_source import ReportsSource

_DAILY_SUFFIX = "/billing/ai-credit-usage.json"


class S3ReportsSource(ReportsSource):
    def __init__(self, bucket=None, prefix=None, client=None) -> None:
        self.bucket = bucket or os.getenv("REPORTS_S3_BUCKET")
        if not self.bucket:
            raise ValueError("REPORTS_S3_BUCKET is required when REPORTS_SOURCE=s3")
        self.prefix = (prefix or os.getenv("REPORTS_S3_PREFIX") or "reports").strip("/")
        if client is not None:
            self._client = client
        else:
            import boto3

            region = os.getenv("AWS_DEFAULT_REGION") or "eu-west-2"
            self._client = boto3.client("s3", region_name=region)

    def _list_keys(self, prefix: str) -> list[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys

    def _get_json(self, key: str) -> dict:
        body = self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        return json.loads(body)

    def _day_from_key(self, key: str) -> str:
        # reports/2026-06-01/billing/ai-credit-usage.json -> 2026-06-01
        rel = key[len(self.prefix):].lstrip("/")
        return rel.split("/")[0]

    def daily_docs(self) -> dict[str, dict]:
        docs: dict[str, dict] = {}
        for key in self._list_keys(f"{self.prefix}/"):
            if key.endswith(_DAILY_SUFFIX):
                docs[self._day_from_key(key)] = self._get_json(key)
        return dict(sorted(docs.items()))

    def per_user_docs(self, day: str) -> dict[str, list]:
        prefix = f"{self.prefix}/{day}/billing/per-user/"
        out: dict[str, list] = {}
        for key in self._list_keys(prefix):
            if not key.endswith(".json"):
                continue
            login = os.path.splitext(os.path.basename(key))[0]
            out[login] = self._get_json(key).get("usageItems", [])
        return out

    def weekly_records(self) -> list[dict]:
        raise NotImplementedError
