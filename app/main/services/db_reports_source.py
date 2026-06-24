"""Athena-backed reports source.

Queries an Athena table over partitioned Parquet (one row per day/user, written
by the producer's build_credit_rows) and returns the same shapes the on-disk and
S3 sources return. Selected when REPORTS_SOURCE=db.

Config (env):
* ATHENA_DATABASE        - Glue database (required).
* ATHENA_TABLE           - table name (required).
* ATHENA_OUTPUT_LOCATION - s3://.../ results staging dir (required).
* ATHENA_WORKGROUP       - workgroup (default "primary").
* AWS_DEFAULT_REGION     - region for the boto3 client (default "eu-west-2").

Credentials are resolved by boto3's default chain (IRSA / the pod's service
account role) - no static keys are read or stored here.

Limitations: the Parquet has no net-amount column, so netAmount is left unset
(consumers default it to 0.0); daily_docs() reads all partitions by contract.
"""

from __future__ import annotations

import os
import time
from datetime import date

from app.main.services import weekly_per_user as wpu
from app.main.services.reports_source import ReportsSource

_POLL_SECONDS = 1.0
_MAX_POLLS = 300  # ~5 min ceiling at 1s between polls


def _item(row: dict) -> dict:
    """One Athena row -> one usageItem (no netAmount; defaults to 0.0 downstream)."""
    return {
        "model": row["model"],
        "grossQuantity": float(row["gross_quantity"]),
        "grossAmount": float(row["gross_amount"]),
    }


class DbReportsSource(ReportsSource):
    def __init__(self, database=None, table=None, output_location=None,
                 workgroup=None, client=None, sleep=None) -> None:
        self.database = database or os.getenv("ATHENA_DATABASE")
        if not self.database:
            raise ValueError("ATHENA_DATABASE is required when REPORTS_SOURCE=db")
        self.table = table or os.getenv("ATHENA_TABLE")
        if not self.table:
            raise ValueError("ATHENA_TABLE is required when REPORTS_SOURCE=db")
        self.output_location = output_location or os.getenv("ATHENA_OUTPUT_LOCATION")
        if not self.output_location:
            raise ValueError(
                "ATHENA_OUTPUT_LOCATION is required when REPORTS_SOURCE=db")
        self.workgroup = workgroup or os.getenv("ATHENA_WORKGROUP") or "primary"
        self._sleep = sleep or time.sleep
        if client is not None:
            self._client = client
        else:
            import boto3  # pylint: disable=import-outside-toplevel

            region = os.getenv("AWS_DEFAULT_REGION") or "eu-west-2"
            self._client = boto3.client("athena", region_name=region)

    def _run_query(self, sql: str) -> list[dict]:
        start = self._client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": self.database},
            ResultConfiguration={"OutputLocation": self.output_location},
            WorkGroup=self.workgroup,
        )
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
        token = None
        while True:
            kwargs = {"QueryExecutionId": qid}
            if token:
                kwargs["NextToken"] = token
            resp = self._client.get_query_results(**kwargs)
            result_rows = resp["ResultSet"]["Rows"]
            if header is None:
                header = [c.get("VarCharValue") for c in result_rows[0]["Data"]]
                result_rows = result_rows[1:]
            for r in result_rows:
                values = [c.get("VarCharValue") for c in r["Data"]]
                rows.append(dict(zip(header, values)))
            token = resp.get("NextToken")
            if not token:
                break
        return rows

    def daily_docs(self) -> dict[str, dict]:
        raise NotImplementedError  # Task 4

    def per_user_docs(self, day: str) -> dict[str, list]:
        d = date.fromisoformat(day)  # raises ValueError on bad input
        sql = (
            'SELECT "user", model, gross_quantity, gross_amount '
            f"FROM {self.table} "
            f"WHERE year = {d.year} AND month = {d.month} AND day = {d.day}"
        )
        out: dict[str, list] = {}
        for row in self._run_query(sql):
            out.setdefault(row["user"], []).append(_item(row))
        return out

    def weekly_records(self) -> list[dict]:
        raise NotImplementedError  # Task 3
