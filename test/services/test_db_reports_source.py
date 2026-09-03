"""Tests for DbReportsSource — Athena SQL backend.

Injects a fake Athena client (boto3 kwargs are PascalCase) and a no-op sleep,
mirroring the project's DI style. No real AWS.
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


# ------------------------------------------------------------------ telemetry
TELEMETRY_ENV = {
    "ATHENA_DATABASE": "db",
    "ATHENA_TABLE_TELEMETRY_USERS": "telemetry_by_user",
    "ATHENA_TABLE_TELEMETRY_ACTIVITY": "telemetry_by_user_activity",
}


def _telemetry_source(monkeypatch, client, env=None):
    for key, value in (env if env is not None else TELEMETRY_ENV).items():
        monkeypatch.setenv(key, value)
    return DbReportsSource(client=client, sleep=lambda _s: None)


def test_telemetry_unavailable_without_table_names(monkeypatch):
    """No table names means no section, which is the development-only gate."""
    monkeypatch.setenv("ATHENA_DATABASE", "db")
    monkeypatch.delenv("ATHENA_TABLE_TELEMETRY_USERS", raising=False)
    monkeypatch.delenv("ATHENA_TABLE_TELEMETRY_ACTIVITY", raising=False)
    source = DbReportsSource(client=FakeAthenaClient(), sleep=lambda _s: None)
    assert source.telemetry_available() is False
    assert source.telemetry_user_rows("alice", "2026-08-01", "2026-08-31") == []
    assert source.telemetry_activity_rows("alice", "2026-08-01", "2026-08-31") == []


def test_telemetry_unavailable_with_only_one_table_name(monkeypatch):
    env = dict(TELEMETRY_ENV)
    del env["ATHENA_TABLE_TELEMETRY_ACTIVITY"]
    monkeypatch.delenv("ATHENA_TABLE_TELEMETRY_ACTIVITY", raising=False)
    source = _telemetry_source(monkeypatch, FakeAthenaClient(), env)
    assert source.telemetry_available() is False


def test_telemetry_available_with_both_table_names(monkeypatch):
    source = _telemetry_source(monkeypatch, FakeAthenaClient())
    assert source.telemetry_available() is True


def test_user_query_filters_by_person_and_day_range(monkeypatch):
    client = FakeAthenaClient(_result_set([], []))
    _telemetry_source(monkeypatch, client).telemetry_user_rows(
        "alice", "2026-08-01", "2026-08-31")
    sql = client.queries[0]
    assert "FROM telemetry_by_user" in sql
    assert "user_login = 'alice'" in sql
    assert "day >= '2026-08-01'" in sql
    assert "day <= '2026-08-31'" in sql
    # Only the columns the page uses, so the scan stays narrow.
    assert "SELECT *" not in sql
    assert "user_initiated_interaction_count" in sql


def test_activity_query_filters_by_person_and_day_range(monkeypatch):
    client = FakeAthenaClient(_result_set([], []))
    _telemetry_source(monkeypatch, client).telemetry_activity_rows(
        "alice", "2026-08-01", "2026-08-31")
    sql = client.queries[0]
    assert "FROM telemetry_by_user_activity" in sql
    assert "user_login = 'alice'" in sql
    assert "SELECT *" not in sql


def test_user_rows_are_converted_to_the_named_shape(monkeypatch):
    header = ["day", "user_initiated_interaction_count",
              "code_generation_activity_count", "code_acceptance_activity_count",
              "loc_added_sum", "loc_deleted_sum", "loc_suggested_to_add_sum",
              "has_activity_telemetry", "used_copilot_code_review_active",
              "used_copilot_code_review_passive"]
    client = FakeAthenaClient(_result_set(
        header, [["2026-08-01", "10", "40", "18", "320", "40", "200",
                  "true", "true", "false"]]))
    rows = _telemetry_source(monkeypatch, client).telemetry_user_rows(
        "alice", "2026-08-01", "2026-08-31")
    assert rows == [{
        "day": "2026-08-01", "interactions": 10, "suggested": 40, "accepted": 18,
        "lines_added": 320, "lines_deleted": 40, "lines_suggested_added": 200,
        "has_telemetry": True, "review_requested": True, "review_automatic": False,
    }]


def test_activity_rows_keep_their_text_columns_as_text(monkeypatch):
    header = ["day", "language", "feature", "mode",
              "code_generation_activity_count", "code_acceptance_activity_count",
              "loc_added_sum", "loc_suggested_to_add_sum"]
    client = FakeAthenaClient(_result_set(
        header, [["2026-08-01", "python", "code_completion",
                  "Inline completion", "40", "18", "320", "200"]]))
    rows = _telemetry_source(monkeypatch, client).telemetry_activity_rows(
        "alice", "2026-08-01", "2026-08-31")
    assert rows == [{
        "day": "2026-08-01", "language": "python", "feature": "code_completion",
        "mode": "Inline completion", "suggested": 40, "accepted": 18,
        "lines_added": 320, "lines_suggested_added": 200,
    }]


def test_missing_values_come_back_as_none_not_zero(monkeypatch):
    """Athena omits VarCharValue for a null. Reading that as 0 would report a
    person as inactive when GitHub simply sent nothing."""
    header = ["day", "user_initiated_interaction_count",
              "code_generation_activity_count", "code_acceptance_activity_count",
              "loc_added_sum", "loc_deleted_sum", "loc_suggested_to_add_sum",
              "has_activity_telemetry", "used_copilot_code_review_active",
              "used_copilot_code_review_passive"]
    page = {"ResultSet": {"Rows": [
        _row(header),
        {"Data": [{"VarCharValue": "2026-08-01"}, {}, {}, {}, {}, {}, {},
                  {"VarCharValue": "false"}, {}, {}]},
    ]}}
    client = FakeAthenaClient(pages=[page])
    row = _telemetry_source(monkeypatch, client).telemetry_user_rows(
        "alice", "2026-08-01", "2026-08-31")[0]
    assert row["interactions"] is None
    assert row["suggested"] is None
    assert row["has_telemetry"] is False
    assert row["review_requested"] is None


@pytest.mark.parametrize("login", [
    "alice'; DROP TABLE telemetry_by_user; --",
    "alice OR 1=1",
    "alice bob",
    "-alice",
    "a" * 40,
    "",
])
def test_an_invalid_username_is_rejected_before_any_query(monkeypatch, login):
    """The username reaches this code from a URL query parameter."""
    client = FakeAthenaClient(_result_set([], []))
    source = _telemetry_source(monkeypatch, client)
    with pytest.raises(ValueError):
        source.telemetry_user_rows(login, "2026-08-01", "2026-08-31")
    assert client.queries == []


@pytest.mark.parametrize("start,end", [
    ("2026-08-01", "2026-08-31 OR 1=1"),
    ("not-a-date", "2026-08-31"),
    ("2026-8-1", "2026-08-31"),
])
def test_an_invalid_date_is_rejected_before_any_query(monkeypatch, start, end):
    client = FakeAthenaClient(_result_set([], []))
    source = _telemetry_source(monkeypatch, client)
    with pytest.raises(ValueError):
        source.telemetry_user_rows("alice", start, end)
    assert client.queries == []


def test_a_hyphenated_username_is_accepted(monkeypatch):
    """Real GitHub logins contain hyphens; the validator must not reject them."""
    client = FakeAthenaClient(_result_set([], []))
    source = _telemetry_source(monkeypatch, client)
    source.telemetry_user_rows("some-real-login", "2026-08-01", "2026-08-31")
    assert "user_login = 'some-real-login'" in client.queries[0]
