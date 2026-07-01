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
