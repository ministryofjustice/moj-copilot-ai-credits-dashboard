from app.main.services.reports_source import LocalFsReportsSource
from services.parquet_fixtures import write_model_partition, write_user_partition


def test_model_rows_reads_partitions_with_day(tmp_path):
    write_model_partition(str(tmp_path), "2026-06-01",
                          [("Claude Opus 4.6", "Opus", False, 100.0),
                           ("Auto: Claude Haiku 4.5", "Haiku", True, 5.0)])
    rows = LocalFsReportsSource(str(tmp_path)).model_rows()
    by_model = {r["model"]: r for r in rows}
    assert by_model["Claude Opus 4.6"] == {
        "day": "2026-06-01", "model": "Claude Opus 4.6",
        "model_family": "Opus", "routed": False, "credits": 100.0}
    assert by_model["Auto: Claude Haiku 4.5"]["routed"] is True


def test_user_rows_reads_partitions_with_day(tmp_path):
    write_user_partition(str(tmp_path), "2026-06-02", [("alice", 12.5), ("bob", 3.0)])
    rows = LocalFsReportsSource(str(tmp_path)).user_rows()
    assert {"day": "2026-06-02", "user_login": "alice", "credits": 12.5} in rows
