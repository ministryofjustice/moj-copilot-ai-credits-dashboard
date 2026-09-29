"""Tests for telemetry reading in LocalFsReportsSource.

The reader filters by person and day range at the storage layer rather than
fetching whole tables, because telemetry_by_user_activity holds one row per
person per day per language per feature. Nulls must survive the read: the
pipeline writes a genuinely absent value as null, and turning it into zero
would report a person as inactive when the truth is that no data arrived.
"""

from app.main.services.reports_source import (
    LocalFsReportsSource,
    ORG_TELEMETRY_USER_COLUMNS,
)
from services.parquet_fixtures import (
    write_telemetry_activity_partition,
    write_telemetry_user_partition,
    write_user_partition,
)


def _user_row(login, **overrides):
    row = {
        "user_login": login,
        "user_initiated_interaction_count": 10,
        "code_generation_activity_count": 40,
        "code_acceptance_activity_count": 18,
        "loc_suggested_to_add_sum": 200,
        "loc_added_sum": 320,
        "loc_deleted_sum": 40,
        "has_activity_telemetry": True,
        "used_copilot_code_review_active": True,
        "used_copilot_code_review_passive": False,
        "ai_credits_used": 1.5,
    }
    row.update(overrides)
    return row


def _activity_row(login, language, feature, mode, **overrides):
    row = {
        "user_login": login, "language": language,
        "feature": feature, "mode": mode,
        "code_generation_activity_count": 40,
        "code_acceptance_activity_count": 18,
        "loc_suggested_to_add_sum": 200,
        "loc_added_sum": 320,
        "loc_deleted_sum": 40,
    }
    row.update(overrides)
    return row


def test_telemetry_unavailable_when_folders_absent(tmp_path):
    """A checkout with only the credit tables must not offer telemetry."""
    write_user_partition(str(tmp_path), "2026-08-01", [("alice", 1.0)])
    assert LocalFsReportsSource(str(tmp_path)).telemetry_available() is False


def test_telemetry_unavailable_when_only_one_folder_present(tmp_path):
    write_telemetry_user_partition(str(tmp_path), "2026-08-01", [_user_row("alice")])
    assert LocalFsReportsSource(str(tmp_path)).telemetry_available() is False


def test_telemetry_available_when_both_folders_present(tmp_path):
    write_telemetry_user_partition(str(tmp_path), "2026-08-01", [_user_row("alice")])
    write_telemetry_activity_partition(
        str(tmp_path), "2026-08-01",
        [_activity_row("alice", "python", "code_completion", "Inline completion")])
    assert LocalFsReportsSource(str(tmp_path)).telemetry_available() is True


def test_user_rows_return_the_named_shape(tmp_path):
    write_telemetry_user_partition(str(tmp_path), "2026-08-01", [_user_row("alice")])
    rows = LocalFsReportsSource(str(tmp_path)).telemetry_user_rows(
        "alice", "2026-08-01", "2026-08-31")
    assert rows == [{
        "day": "2026-08-01", "interactions": 10, "suggested": 40, "accepted": 18,
        "lines_added": 320, "lines_deleted": 40, "lines_suggested_added": 200,
        "has_telemetry": True, "review_requested": True, "review_automatic": False,
    }]


def test_user_rows_exclude_other_people(tmp_path):
    write_telemetry_user_partition(
        str(tmp_path), "2026-08-01", [_user_row("alice"), _user_row("bob")])
    rows = LocalFsReportsSource(str(tmp_path)).telemetry_user_rows(
        "bob", "2026-08-01", "2026-08-31")
    assert len(rows) == 1


def test_user_rows_exclude_days_outside_the_range(tmp_path):
    for day in ("2026-07-31", "2026-08-15", "2026-09-01"):
        write_telemetry_user_partition(str(tmp_path), day, [_user_row("alice")])
    rows = LocalFsReportsSource(str(tmp_path)).telemetry_user_rows(
        "alice", "2026-08-01", "2026-08-31")
    assert [r["day"] for r in rows] == ["2026-08-15"]


def test_user_rows_preserve_nulls_as_none(tmp_path):
    """A reduced-shape record: GitHub sent no activity telemetry that day."""
    write_telemetry_user_partition(str(tmp_path), "2026-08-02", [_user_row(
        "alice",
        user_initiated_interaction_count=None,
        code_generation_activity_count=None,
        has_activity_telemetry=False,
        used_copilot_code_review_active=None,
        used_copilot_code_review_passive=None,
    )])
    row = LocalFsReportsSource(str(tmp_path)).telemetry_user_rows(
        "alice", "2026-08-01", "2026-08-31")[0]
    assert row["interactions"] is None
    assert row["suggested"] is None
    assert row["has_telemetry"] is False
    assert row["review_requested"] is None
    assert row["review_automatic"] is None


def test_activity_rows_return_the_named_shape(tmp_path):
    write_telemetry_activity_partition(
        str(tmp_path), "2026-08-01",
        [_activity_row("alice", "ts", "code_completion", "Inline completion")])
    rows = LocalFsReportsSource(str(tmp_path)).telemetry_activity_rows(
        "alice", "2026-08-01", "2026-08-31")
    assert rows == [{
        "day": "2026-08-01", "language": "ts", "feature": "code_completion",
        "mode": "Inline completion", "suggested": 40, "accepted": 18,
        "lines_added": 320, "lines_suggested_added": 200,
    }]


def test_activity_rows_exclude_other_people_and_days(tmp_path):
    write_telemetry_activity_partition(str(tmp_path), "2026-08-01", [
        _activity_row("alice", "python", "code_completion", "Inline completion"),
        _activity_row("bob", "python", "code_completion", "Inline completion"),
    ])
    write_telemetry_activity_partition(
        str(tmp_path), "2026-09-01",
        [_activity_row("alice", "go", "chat_panel_agent_mode", "Agent mode")])
    rows = LocalFsReportsSource(str(tmp_path)).telemetry_activity_rows(
        "alice", "2026-08-01", "2026-08-31")
    assert [(r["day"], r["language"]) for r in rows] == [("2026-08-01", "python")]


def test_rows_are_empty_for_a_person_with_no_data(tmp_path):
    write_telemetry_user_partition(str(tmp_path), "2026-08-01", [_user_row("alice")])
    write_telemetry_activity_partition(
        str(tmp_path), "2026-08-01",
        [_activity_row("alice", "python", "code_completion", "Inline completion")])
    source = LocalFsReportsSource(str(tmp_path))
    assert source.telemetry_user_rows("nobody", "2026-08-01", "2026-08-31") == []
    assert source.telemetry_activity_rows("nobody", "2026-08-01", "2026-08-31") == []


# ------------------------------------------------------------ org-wide reads

def test_org_user_rows_include_everyone_in_the_range(tmp_path):
    write_telemetry_user_partition(str(tmp_path), "2026-07-31", [_user_row("alice")])
    write_telemetry_user_partition(
        str(tmp_path), "2026-08-01", [_user_row("alice"), _user_row("bob")])
    rows = LocalFsReportsSource(str(tmp_path)).org_telemetry_user_rows(
        "2026-08-01", "2026-08-31")
    assert sorted(r["user_login"] for r in rows) == ["alice", "bob"]
    assert {r["day"] for r in rows} == {"2026-08-01"}


def test_org_user_rows_carry_the_org_columns(tmp_path):
    write_telemetry_user_partition(str(tmp_path), "2026-08-01", [_user_row(
        "alice", used_chat=True, used_copilot_app=False,
        cli_request_count=7, app_request_count=None, cli_prompt_count=3)])
    row = LocalFsReportsSource(str(tmp_path)).org_telemetry_user_rows(
        "2026-08-01", "2026-08-31")[0]
    assert row["user_login"] == "alice"
    assert row["credits"] == 1.5
    assert row["suggested"] == 40
    assert row["used_chat"] is True
    assert row["used_app"] is False
    assert row["used_agent"] is None
    assert row["cli_requests"] == 7
    assert row["app_requests"] is None
    assert row["cli_prompts"] == 3


def test_org_columns_never_include_tokens():
    assert not [name for name in ORG_TELEMETRY_USER_COLUMNS if "token" in name]


def test_org_activity_rows_include_everyone_with_their_login(tmp_path):
    write_telemetry_activity_partition(str(tmp_path), "2026-08-01", [
        _activity_row("alice", "python", "code_completion", "Inline completion"),
        _activity_row("bob", "go", "chat_panel_agent_mode", "Agent mode"),
    ])
    write_telemetry_activity_partition(
        str(tmp_path), "2026-09-01",
        [_activity_row("alice", "go", "chat_panel_agent_mode", "Agent mode")])
    rows = LocalFsReportsSource(str(tmp_path)).org_telemetry_activity_rows(
        "2026-08-01", "2026-08-31")
    assert sorted((r["user_login"], r["language"]) for r in rows) == [
        ("alice", "python"), ("bob", "go")]


def test_org_months_lists_each_month_once_in_order(tmp_path):
    for day in ("2026-08-02", "2026-07-30", "2026-08-01"):
        write_telemetry_user_partition(str(tmp_path), day, [_user_row("alice")])
    assert LocalFsReportsSource(str(tmp_path)).org_telemetry_months() == [
        "2026-07", "2026-08"]


def test_org_reads_are_empty_without_the_telemetry_tables(tmp_path):
    write_user_partition(str(tmp_path), "2026-08-01", [("alice", 1.0)])
    source = LocalFsReportsSource(str(tmp_path))
    assert source.org_telemetry_months() == []
    assert source.org_telemetry_user_rows("2026-08-01", "2026-08-31") == []
    assert source.org_telemetry_activity_rows("2026-08-01", "2026-08-31") == []
