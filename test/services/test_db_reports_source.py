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


def test_per_user_docs_groups_by_login_and_casts():
    rows = _result_set(
        ["user", "model", "gross_quantity", "gross_amount"],
        [["alice", "AI Credits", "5", "0.05"],
         ["bob", "AI Credits", "3", "0.03"]],
    )
    src = _source(rows)
    docs = src.per_user_docs("2026-06-01")
    assert docs == {
        "alice": [{"model": "AI Credits", "grossQuantity": 5.0, "grossAmount": 0.05}],
        "bob": [{"model": "AI Credits", "grossQuantity": 3.0, "grossAmount": 0.03}],
    }


def test_per_user_docs_partition_filters_by_date():
    client = FakeAthenaClient(_result_set(
        ["user", "model", "gross_quantity", "gross_amount"], []))
    src = DbReportsSource(database="db", table="t", output_location="s3://x/",
                          client=client, sleep=lambda _s: None)
    src.per_user_docs("2026-06-04")
    sql = client.queries[0]
    assert "year = 2026" in sql and "month = 6" in sql and "day = 4" in sql
    assert '"user"' in sql  # reserved word is quoted


def test_per_user_docs_rejects_bad_day():
    src = _source()
    with pytest.raises(ValueError):
        src.per_user_docs("not-a-date")


def test_weekly_records_shape_and_per_model():
    rows = _result_set(
        ["year", "month", "day", "user", "model", "credits", "usd"],
        [["2026", "6", "1", "alice", "AI Credits", "100", "1.0"],
         ["2026", "6", "2", "alice", "AI Credits", "10", "0.1"]],
    )
    src = _source(rows)
    records = src.weekly_records()
    assert {(r["day"], r["user"]) for r in records} == {
        ("2026-06-01", "alice"), ("2026-06-02", "alice")}
    day1 = next(r for r in records if r["day"] == "2026-06-01")
    assert day1["credits"] == pytest.approx(100.0)
    assert day1["usd"] == pytest.approx(1.0)
    assert day1["per_model"] == {"AI Credits": pytest.approx(100.0)}


def test_weekly_records_uses_group_by():
    client = FakeAthenaClient(_result_set(
        ["year", "month", "day", "user", "model", "credits", "usd"], []))
    src = DbReportsSource(database="db", table="t", output_location="s3://x/",
                          client=client, sleep=lambda _s: None)
    src.weekly_records()
    assert "GROUP BY" in client.queries[0]


def test_weekly_records_skips_zero_credit_users():
    rows = _result_set(
        ["year", "month", "day", "user", "model", "credits", "usd"],
        [["2026", "6", "1", "idle", "AI Credits", "0", "0.0"]],
    )
    src = _source(rows)
    assert not src.weekly_records()


def test_daily_docs_grouped_by_day_sorted():
    rows = _result_set(
        ["year", "month", "day", "enterprise", "user",
         "model", "gross_quantity", "gross_amount"],
        [["2026", "6", "2", "MoJ", "alice", "AI Credits", "5", "0.05"],
         ["2026", "6", "1", "MoJ", "bob", "AI Credits", "3", "0.03"],
         ["2026", "6", "1", "MoJ", "carol", "AI Credits", "2", "0.02"]],
    )
    src = _source(rows)
    docs = src.daily_docs()
    assert list(docs) == ["2026-06-01", "2026-06-02"]
    assert docs["2026-06-01"]["enterprise"] == "MoJ"
    assert docs["2026-06-01"]["usageItems"] == [
        {"model": "AI Credits", "grossQuantity": 3.0, "grossAmount": 0.03},
        {"model": "AI Credits", "grossQuantity": 2.0, "grossAmount": 0.02},
    ]
    assert docs["2026-06-02"]["usageItems"] == [
        {"model": "AI Credits", "grossQuantity": 5.0, "grossAmount": 0.05}]
