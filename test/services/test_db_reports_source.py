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


class FakePaginator:
    """Stand-in for a boto3 paginator: yields the configured pages in order."""

    def __init__(self, pages):
        self._pages = pages

    def paginate(self, **kw):
        return iter(self._pages)


class FakeAthenaClient:
    """In-memory stand-in for a boto3 'athena' client.

    `states` drives the poll loop (last value repeats). Results come back via a
    paginator (as in real boto3): `pages` is the list of GetQueryResults payloads,
    defaulting to a single page built from `result_set`. Captured SQL via `.queries`.
    """

    def __init__(self, result_set=None, states=("SUCCEEDED",), pages=None):
        self._pages = pages if pages is not None else [
            result_set or _result_set([], [])]
        self._states = list(states)
        self.queries = []
        self.last_start_kwargs = None

    def start_query_execution(self, **kw):
        self.queries.append(kw["QueryString"])
        self.last_start_kwargs = kw
        return {"QueryExecutionId": "qid-1"}

    def get_query_execution(self, QueryExecutionId):  # noqa: N803
        state = self._states.pop(0) if len(self._states) > 1 else self._states[0]
        return {"QueryExecution": {"Status": {
            "State": state, "StateChangeReason": "boom"}}}

    def get_paginator(self, name):
        return FakePaginator(self._pages)


def _source(result_set=None, states=("SUCCEEDED",)):
    return DbReportsSource(
        database="db", output_location="s3://staging/",
        client=FakeAthenaClient(result_set, states), sleep=lambda _s: None,
    )


# ---------------------------------------------------------------- query plumbing
def test_run_query_maps_rows_to_dicts():
    src = _source(_result_set(["a", "b"], [["1", "x"], ["2", "y"]]))
    assert src._run_query("SELECT a, b FROM t") == [
        {"a": "1", "b": "x"}, {"a": "2", "b": "y"},
    ]


def test_run_query_concatenates_paginated_pages():
    # Real Athena puts the header only on the first page; later pages are data-only.
    page1 = _result_set(["a"], [["1"]])
    page2 = {"ResultSet": {"Rows": [_row(["2"])]}}
    client = FakeAthenaClient(pages=[page1, page2])
    src = DbReportsSource(database="db", output_location="s3://x/",
                          client=client, sleep=lambda _s: None)
    assert src._run_query("SELECT a FROM t") == [{"a": "1"}, {"a": "2"}]


def test_run_query_handles_empty_page():
    client = FakeAthenaClient(pages=[{"ResultSet": {"Rows": []}}])
    src = DbReportsSource(database="db", output_location="s3://x/",
                          client=client, sleep=lambda _s: None)
    assert not src._run_query("SELECT a FROM t")


def test_run_query_polls_until_succeeded():
    client = FakeAthenaClient(_result_set(["a"], [["1"]]),
                              states=("QUEUED", "RUNNING", "SUCCEEDED"))
    src = DbReportsSource(database="db", output_location="s3://x/",
                          client=client, sleep=lambda _s: None)
    assert src._run_query("SELECT a FROM t") == [{"a": "1"}]


def test_run_query_raises_on_failed():
    src = _source(states=("FAILED",))
    with pytest.raises(RuntimeError, match="FAILED"):
        src._run_query("SELECT 1")


# ---------------------------------------------------------------- config guards
def test_missing_database_raises(monkeypatch):
    monkeypatch.delenv("ATHENA_DATABASE", raising=False)
    with pytest.raises(ValueError, match="ATHENA_DATABASE"):
        DbReportsSource(output_location="s3://x/", client=FakeAthenaClient())


def test_missing_output_location_omits_result_configuration(monkeypatch):
    # No output location -> rely on the workgroup's default; Athena is called
    # without ResultConfiguration rather than erroring.
    monkeypatch.delenv("ATHENA_OUTPUT_LOCATION", raising=False)
    client = FakeAthenaClient(_result_set(["a"], [["1"]]))
    src = DbReportsSource(database="db", client=client, sleep=lambda _s: None)
    src._run_query("SELECT a FROM t")
    assert "ResultConfiguration" not in client.last_start_kwargs


def test_output_location_sets_result_configuration():
    client = FakeAthenaClient(_result_set(["a"], [["1"]]))
    src = DbReportsSource(database="db", output_location="s3://stg/",
                          client=client, sleep=lambda _s: None)
    src._run_query("SELECT a FROM t")
    assert client.last_start_kwargs["ResultConfiguration"] == {
        "OutputLocation": "s3://stg/"}


def test_start_query_passes_sql():
    client = FakeAthenaClient(_result_set(["a"], []))
    src = DbReportsSource(database="mydb", output_location="s3://stg/",
                          workgroup="wg", client=client, sleep=lambda _s: None)
    src._run_query("SELECT a FROM t")
    assert client.queries == ["SELECT a FROM t"]


# ------------------------------------------------------------------- model_rows
def test_model_rows_parses_routed_and_credits():
    rows = _result_set(
        ["model", "model_family", "routed", "ai_credits_used", "day"],
        [["Opus 4.6", "Opus", "false", "100.5", "2026-06-01"],
         ["Auto: Haiku", "Haiku", "true", "5.0", "2026-06-01"]],
    )
    src = _source(rows)
    out = src.model_rows()
    assert out[0] == {"day": "2026-06-01", "model": "Opus 4.6",
                      "model_family": "Opus", "routed": False, "credits": 100.5}
    assert out[1]["routed"] is True


def test_model_rows_queries_model_table():
    client = FakeAthenaClient(_result_set(
        ["model", "model_family", "routed", "ai_credits_used", "day"], []))
    src = DbReportsSource(database="db", model_table="cbm", output_location="s3://x/",
                          client=client, sleep=lambda _s: None)
    src.model_rows()
    assert "FROM cbm" in client.queries[0]


# -------------------------------------------------------------------- user_rows
def test_user_rows_parses_credits():
    rows = _result_set(
        ["user_login", "ai_credits_used", "day"],
        [["alice", "10324.7", "2026-06-01"], ["bob", "3.0", "2026-06-01"]],
    )
    src = _source(rows)
    assert src.user_rows() == [
        {"day": "2026-06-01", "user_login": "alice", "credits": 10324.7},
        {"day": "2026-06-01", "user_login": "bob", "credits": 3.0},
    ]


def test_user_rows_queries_user_table():
    client = FakeAthenaClient(_result_set(["user_login", "ai_credits_used", "day"], []))
    src = DbReportsSource(database="db", user_table="cbu", output_location="s3://x/",
                          client=client, sleep=lambda _s: None)
    src.user_rows()
    assert "FROM cbu" in client.queries[0]
