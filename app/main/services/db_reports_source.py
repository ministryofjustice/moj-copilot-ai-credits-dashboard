"""Athena-backed reports source.

Queries the two Athena tables over the partitioned Parquet (`credits_by_model`,
`credits_by_user`) and returns the same row-lists the local and S3 sources return.
Selected when REPORTS_SOURCE=db.

Config (env):
* ATHENA_DATABASE        - Glue database (required).
* ATHENA_TABLE_MODELS    - per-model table name (default "credits_by_model").
* ATHENA_TABLE_USERS     - per-user table name (default "credits_by_user").
* ATHENA_OUTPUT_LOCATION - s3://.../ results staging dir (optional; when unset,
                           Athena uses the workgroup's default output location).
* ATHENA_WORKGROUP       - workgroup (default "primary").
* AWS_DEFAULT_REGION     - region for the boto3 client (default "eu-west-2").

Credentials are resolved by boto3's default chain (IRSA / the pod's service
account role) - no static keys are read or stored here.
"""

from __future__ import annotations

import os
import time

from app.main.services.reports_source import ReportsSource

_POLL_SECONDS = 1.0
_MAX_POLLS = 300  # ~5 min ceiling at 1s between polls


class DbReportsSource(ReportsSource):
    def __init__(self, database=None, model_table=None, user_table=None,  # pylint: disable=too-many-arguments
                 output_location=None, *, workgroup=None, client=None,
                 sleep=None) -> None:
        self.database = database or os.getenv("ATHENA_DATABASE")
        if not self.database:
            raise ValueError("ATHENA_DATABASE is required when REPORTS_SOURCE=db")
        self.model_table = (model_table or os.getenv("ATHENA_TABLE_MODELS")
                            or "credits_by_model")
        self.user_table = (user_table or os.getenv("ATHENA_TABLE_USERS")
                           or "credits_by_user")
        # Optional: when unset, Athena writes results to the workgroup's own
        # default output location (result_configuration on the workgroup).
        self.output_location = output_location or os.getenv("ATHENA_OUTPUT_LOCATION")
        self.workgroup = workgroup or os.getenv("ATHENA_WORKGROUP") or "primary"
        self._sleep = sleep or time.sleep
        if client is not None:
            self._client = client
        else:
            import boto3  # pylint: disable=import-outside-toplevel

            region = os.getenv("AWS_DEFAULT_REGION") or "eu-west-2"
            self._client = boto3.client("athena", region_name=region)

    def _run_query(self, sql: str) -> list[dict]:
        params = {
            "QueryString": sql,
            "QueryExecutionContext": {"Database": self.database},
            "WorkGroup": self.workgroup,
        }
        if self.output_location:
            params["ResultConfiguration"] = {
                "OutputLocation": self.output_location}
        start = self._client.start_query_execution(**params)
        qid = start["QueryExecutionId"]
        for _ in range(_MAX_POLLS):
            status = self._client.get_query_execution(
                QueryExecutionId=qid)["QueryExecution"]["Status"]
            state = status["State"]
            if state == "SUCCEEDED":
                return self._collect_results(qid)
            if state in ("FAILED", "CANCELLED"):
                raise RuntimeError(
                    f"Athena query {state}: {status.get('StateChangeReason', '')}")
            self._sleep(_POLL_SECONDS)
        raise RuntimeError("Athena query timed out")

    def _collect_results(self, qid: str) -> list[dict]:
        rows: list[dict] = []
        header: list[str] | None = None
        paginator = self._client.get_paginator("get_query_results")
        for resp in paginator.paginate(QueryExecutionId=qid):
            result_rows = resp["ResultSet"]["Rows"]
            if header is None:
                if not result_rows:  # no header => no data
                    continue
                header = [c.get("VarCharValue") for c in result_rows[0]["Data"]]
                result_rows = result_rows[1:]
            for r in result_rows:
                values = [c.get("VarCharValue") for c in r["Data"]]
                rows.append(dict(zip(header, values)))
        return rows

    def model_rows(self) -> list[dict]:
        sql = ("SELECT model, model_family, routed, ai_credits_used, day "
               f"FROM {self.model_table}")
        return [
            {"day": r["day"], "model": r["model"], "model_family": r["model_family"],
             "routed": str(r["routed"]).strip().lower() == "true",
             "credits": float(r["ai_credits_used"])}
            for r in self._run_query(sql)
        ]

    def user_rows(self) -> list[dict]:
        sql = f"SELECT user_login, ai_credits_used, day FROM {self.user_table}"
        return [
            {"day": r["day"], "user_login": r["user_login"],
             "credits": float(r["ai_credits_used"])}
            for r in self._run_query(sql)
        ]
