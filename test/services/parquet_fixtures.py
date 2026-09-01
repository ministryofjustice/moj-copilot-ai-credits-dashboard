"""Build small Hive-partitioned parquet trees for tests (no day column in-file)."""
import os
import pyarrow as pa
import pyarrow.parquet as pq


def write_model_partition(root, day, rows):
    """rows: list of (model, model_family, routed, credits)."""
    table = pa.table({
        "model": [r[0] for r in rows],
        "model_family": [r[1] for r in rows],
        "routed": [bool(r[2]) for r in rows],
        "ai_credits_used": [float(r[3]) for r in rows],
    })
    d = os.path.join(root, "credits_by_model", f"day={day}")
    os.makedirs(d, exist_ok=True)
    pq.write_table(table, os.path.join(d, "part-0.parquet"))


def write_user_partition(root, day, rows):
    """rows: list of (user_login, credits)."""
    table = pa.table({
        "user_login": [r[0] for r in rows],
        "ai_credits_used": [float(r[1]) for r in rows],
    })
    d = os.path.join(root, "credits_by_user", f"day={day}")
    os.makedirs(d, exist_ok=True)
    pq.write_table(table, os.path.join(d, "part-0.parquet"))


def write_telemetry_user_partition(root, day, rows):
    """rows: list of dicts with any subset of the telemetry_by_user columns.

    Missing values are written as null, not zero, because that is what the
    pipeline does for a person-day where GitHub sent no activity telemetry.
    """
    columns = {
        "user_id": pa.int64(),
        "user_login": pa.string(),
        "user_initiated_interaction_count": pa.int64(),
        "code_generation_activity_count": pa.int64(),
        "code_acceptance_activity_count": pa.int64(),
        "loc_suggested_to_add_sum": pa.int64(),
        "loc_added_sum": pa.int64(),
        "loc_deleted_sum": pa.int64(),
        "has_activity_telemetry": pa.bool_(),
        "used_copilot_code_review_active": pa.bool_(),
        "used_copilot_code_review_passive": pa.bool_(),
        "ai_credits_used": pa.float64(),
    }
    table = pa.table(
        {name: pa.array([r.get(name) for r in rows], type=kind)
         for name, kind in columns.items()}
    )
    d = os.path.join(root, "telemetry_by_user", f"day={day}")
    os.makedirs(d, exist_ok=True)
    pq.write_table(table, os.path.join(d, "part-0.parquet"))


def write_telemetry_activity_partition(root, day, rows):
    """rows: list of dicts with any subset of the telemetry_by_user_activity
    columns. Missing values are written as null."""
    columns = {
        "user_login": pa.string(),
        "language": pa.string(),
        "feature": pa.string(),
        "mode": pa.string(),
        "code_generation_activity_count": pa.int64(),
        "code_acceptance_activity_count": pa.int64(),
        "loc_suggested_to_add_sum": pa.int64(),
        "loc_added_sum": pa.int64(),
        "loc_deleted_sum": pa.int64(),
    }
    table = pa.table(
        {name: pa.array([r.get(name) for r in rows], type=kind)
         for name, kind in columns.items()}
    )
    d = os.path.join(root, "telemetry_by_user_activity", f"day={day}")
    os.makedirs(d, exist_ok=True)
    pq.write_table(table, os.path.join(d, "part-0.parquet"))
