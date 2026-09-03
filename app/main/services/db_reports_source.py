"""Athena-backed reports source.

Queries the two Athena tables over the partitioned Parquet (`credits_by_model`,
`credits_by_user`) and returns the same row-lists the local source returns.
Selected when REPORTS_SOURCE=db.

Config (env):
* ATHENA_DATABASE        - Glue database (required).
* ATHENA_TABLE_MODELS    - per-model table name (default "credits_by_model").
* ATHENA_TABLE_USERS     - per-user table name (default "credits_by_user").
* ATHENA_OUTPUT_LOCATION - s3://.../ results staging dir (optional; when unset,
                           Athena uses the workgroup's default output location).
* ATHENA_WORKGROUP       - workgroup (default "primary").
* AWS_DEFAULT_REGION     - region for the boto3 client (default "eu-west-2").
* ATHENA_TABLE_TELEMETRY_USERS    - per-person-day telemetry table (optional).
* ATHENA_TABLE_TELEMETRY_ACTIVITY - per-language/feature telemetry table (optional).

Both telemetry variables are unset by default. When either is missing,
`telemetry_available()` is False and the dashboard renders no telemetry. That
is how the feature is confined to the development deployment: the development
values file supplies the names and the production one does not.

Credentials are resolved by boto3's default chain (IRSA / the pod's service
account role) - no static keys are read or stored here.
"""

from __future__ import annotations

import os
import re
import time

from app.main.services.reports_source import (
    ReportsSource,
    TELEMETRY_ACTIVITY_COLUMNS,
    TELEMETRY_USER_COLUMNS,
)

# GitHub's own username rule: letters, digits and hyphens, not starting or
# ending with a hyphen, 39 characters at most. Validating against it means no
# quote, semicolon or space can ever reach the SQL string.
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}$")

# Columns holding text rather than a count, passed through unconverted.
_TEXT_COLUMNS = ("language", "feature", "mode")


def _checked_login(login: str) -> str:
    if not isinstance(login, str) or not _LOGIN.match(login):
        raise ValueError("Not a valid GitHub username")
    return login


def _checked_day(day: str) -> str:
    if not isinstance(day, str) or not _DAY.match(day):
        raise ValueError("Day must be an ISO YYYY-MM-DD date")
    return day


def _int_or_none(value):
    """Athena omits VarCharValue for a null, which arrives here as None. A null
    is not a zero: it means GitHub sent nothing for that person-day."""
    return None if value is None or value == "" else int(value)


def _bool_or_none(value):
    if value is None or value == "":
        return None
    return str(value).strip().lower() == "true"


_POLL_SECONDS = 1.0
_MAX_POLLS = 300  # ~5 min ceiling at 1s between polls


class DbReportsSource(ReportsSource):  # pylint: disable=too-many-instance-attributes
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
        # No defaults: an unset name means telemetry is switched off here.
        self.telemetry_user_table = os.getenv("ATHENA_TABLE_TELEMETRY_USERS")
        self.telemetry_activity_table = os.getenv("ATHENA_TABLE_TELEMETRY_ACTIVITY")
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

    def telemetry_available(self) -> bool:
        return bool(self.telemetry_user_table and self.telemetry_activity_table)

    def _telemetry_query(self, table: str, columns: dict, login: str,  # pylint: disable=too-many-arguments
                         start_day: str, end_day: str) -> list[dict]:
        """Run one narrow, filtered telemetry query and rename its columns.

        Only the listed columns are selected and only one person-month is
        scanned, because the activity table holds one row per person per day
        per language per feature.

        The three values are validated against an allow-list before any SQL is
        built, per OWASP input-validation first principles.
        """
        login = _checked_login(login)
        start_day, end_day = _checked_day(start_day), _checked_day(end_day)
        selected = ", ".join(list(columns) + ["day"])
        sql = (f"SELECT {selected} FROM {table} "
               f"WHERE user_login = '{login}' "
               f"AND day >= '{start_day}' AND day <= '{end_day}'")
        rows = []
        for record in self._run_query(sql):
            row = {"day": record["day"]}
            for source_name, output_name in columns.items():
                raw = record.get(source_name)
                if source_name in _TEXT_COLUMNS:
                    row[output_name] = raw
                elif source_name.startswith(("has_", "used_")):
                    row[output_name] = _bool_or_none(raw)
                else:
                    row[output_name] = _int_or_none(raw)
            rows.append(row)
        return rows

    def telemetry_user_rows(self, login: str, start_day: str,
                            end_day: str) -> list[dict]:
        if not self.telemetry_available():
            return []
        return self._telemetry_query(self.telemetry_user_table,
                                     TELEMETRY_USER_COLUMNS,
                                     login, start_day, end_day)

    def telemetry_activity_rows(self, login: str, start_day: str,
                                end_day: str) -> list[dict]:
        if not self.telemetry_available():
            return []
        return self._telemetry_query(self.telemetry_activity_table,
                                     TELEMETRY_ACTIVITY_COLUMNS,
                                     login, start_day, end_day)
