"""Tests for DbReportsSource — Athena SQL backend.

Injects a fake Athena client (boto3 kwargs are PascalCase) and a no-op sleep,
mirroring the project's DI style (see test_s3_reports_source.py). No real AWS.
"""

import pytest

from app.main.services.db_reports_source import DbReportsSource

# pylint: disable=too-few-public-methods,invalid-name,unused-argument,protected-access


def _row(values):
    """One Athena result row: {'Data': [{'VarCharValue': str}, ...]}."""
    return {"Data": [{"VarCharValue": str(v)} for v in values]}


def _result_set(header, data_rows):
    """A single-page GetQueryResults payload (first row is the header)."""
    rows = [_row(header)] + [_row(r) for r in data_rows]
    return {"ResultSet": {"Rows": rows}}


class FakeAthenaClient:
    """In-memory stand-in for a boto3 'athena' client.

    `states` drives the poll loop (last value repeats); `result_set` is what
    get_query_results returns. Captured SQL is exposed via `.queries`.
    """

    def __init__(self, result_set=None, states=("SUCCEEDED",)):
        self._result_set = result_set or _result_set([], [])
        self._states = list(states)
        self.queries = []

    def start_query_execution(self, **kw):
        self.queries.append(kw["QueryString"])
        return {"QueryExecutionId": "qid-1"}

    def get_query_execution(self, QueryExecutionId):  # noqa: N803
        state = self._states.pop(0) if len(self._states) > 1 else self._states[0]
        return {"QueryExecution": {"Status": {
            "State": state, "StateChangeReason": "boom"}}}

    def get_query_results(self, **kw):
        return self._result_set


def _source(result_set=None, states=("SUCCEEDED",)):
    return DbReportsSource(
        database="db", table="t", output_location="s3://staging/",
        client=FakeAthenaClient(result_set, states), sleep=lambda _s: None,
    )


def test_run_query_maps_rows_to_dicts():
    src = _source(_result_set(["a", "b"], [["1", "x"], ["2", "y"]]))
    assert src._run_query("SELECT a, b FROM t") == [
        {"a": "1", "b": "x"}, {"a": "2", "b": "y"},
    ]


def test_run_query_polls_until_succeeded():
    client = FakeAthenaClient(_result_set(["a"], [["1"]]),
                              states=("QUEUED", "RUNNING", "SUCCEEDED"))
    src = DbReportsSource(database="db", table="t", output_location="s3://x/",
                          client=client, sleep=lambda _s: None)
    assert src._run_query("SELECT a FROM t") == [{"a": "1"}]


def test_run_query_raises_on_failed():
    src = _source(states=("FAILED",))
    with pytest.raises(RuntimeError, match="FAILED"):
        src._run_query("SELECT 1")


def test_missing_database_raises(monkeypatch):
    monkeypatch.delenv("ATHENA_DATABASE", raising=False)
    with pytest.raises(ValueError, match="ATHENA_DATABASE"):
        DbReportsSource(table="t", output_location="s3://x/",
                        client=FakeAthenaClient())


def test_missing_table_raises(monkeypatch):
    monkeypatch.delenv("ATHENA_TABLE", raising=False)
    with pytest.raises(ValueError, match="ATHENA_TABLE"):
        DbReportsSource(database="db", output_location="s3://x/",
                        client=FakeAthenaClient())


def test_missing_output_location_raises(monkeypatch):
    monkeypatch.delenv("ATHENA_OUTPUT_LOCATION", raising=False)
    with pytest.raises(ValueError, match="ATHENA_OUTPUT_LOCATION"):
        DbReportsSource(database="db", table="t", client=FakeAthenaClient())


def test_start_query_passes_database_and_output_location():
    client = FakeAthenaClient(_result_set(["a"], []))
    src = DbReportsSource(database="mydb", table="t", output_location="s3://stg/",
                          workgroup="wg", client=client, sleep=lambda _s: None)
    src._run_query("SELECT a FROM t")
    assert client.queries == ["SELECT a FROM t"]
