import json
from datetime import date

from pytest import approx

import app.main.services.weekly_per_user as wpu


def test_iso_week_label_maps_day_to_iso_week():
    assert wpu.iso_week_label("2026-06-01") == ("2026-W23", 2026, 23)
    assert wpu.iso_week_label("2026-06-07") == ("2026-W23", 2026, 23)
    assert wpu.iso_week_label("2026-06-08") == ("2026-W24", 2026, 24)


def test_iso_week_label_handles_year_boundary():
    # 2025-12-29 belongs to ISO week 1 of 2026
    assert wpu.iso_week_label("2025-12-29") == ("2026-W01", 2026, 1)


def test_week_span_returns_monday_and_sunday():
    assert wpu.week_span(2026, 23) == (date(2026, 6, 1), date(2026, 6, 7))
    assert wpu.week_span(2026, 24) == (date(2026, 6, 8), date(2026, 6, 14))


def _rec(day, user, credits_val, usd, per_model):
    return {"day": day, "user": user, "credits": credits_val, "usd": usd,
            "per_model": per_model}


def test_rollup_weekly_sums_user_across_days_in_same_week():
    records = [
        _rec("2026-06-01", "alice", 100.0, 1.0, {"Opus": 100.0}),
        _rec("2026-06-04", "alice", 50.0, 0.5, {"Opus": 40.0, "Haiku": 10.0}),
    ]
    rows = wpu.rollup_weekly(records)
    assert len(rows) == 1
    row = rows[0]
    assert row["week_label"] == "2026-W23"
    assert row["user"] == "alice"
    assert row["credits"] == approx(150.0)
    assert row["usd"] == approx(1.5)
    assert row["day_count"] == 2
    assert row["top_model"] == "Opus"
    assert row["per_model"] == {"Opus": approx(140.0), "Haiku": approx(10.0)}


def test_rollup_weekly_splits_users_and_weeks():
    records = [
        _rec("2026-06-07", "alice", 10.0, 0.1, {"Opus": 10.0}),   # W23
        _rec("2026-06-08", "alice", 20.0, 0.2, {"Opus": 20.0}),   # W24
        _rec("2026-06-08", "bob", 5.0, 0.05, {"Haiku": 5.0}),     # W24
    ]
    rows = wpu.rollup_weekly(records)
    assert len(rows) == 3
    weeks = {r["week_label"] for r in rows}
    assert weeks == {"2026-W23", "2026-W24"}
    alice_w24 = next(
        r for r in rows if r["user"] == "alice" and r["week_label"] == "2026-W24"
    )
    assert alice_w24["credits"] == approx(20.0)


def test_rollup_weekly_empty_returns_empty_list():
    rows = wpu.rollup_weekly([])
    assert not rows


def test_record_from_items_sums_per_model():
    rec = wpu.record_from_items("2026-06-01", "alice", [
        {"model": "Opus", "grossQuantity": 100.0, "grossAmount": 1.0},
        {"model": "Opus", "grossQuantity": 20.0, "grossAmount": 0.2},
        {"model": "Haiku", "grossQuantity": 5.0, "grossAmount": 0.05},
    ])
    assert rec == {
        "day": "2026-06-01", "user": "alice",
        "credits": approx(125.0), "usd": approx(1.25),
        "per_model": {"Opus": approx(120.0), "Haiku": approx(5.0)},
    }


def test_record_from_items_returns_none_when_no_usage():
    assert wpu.record_from_items("2026-06-01", "empty", []) is None
    assert wpu.record_from_items("2026-06-01", "zero", [
        {"model": "Opus", "grossQuantity": 0.0, "grossAmount": 0.0},
    ]) is None


def _write_per_user(tmp_path, day, login, items):
    d = tmp_path / "reports" / day / "billing" / "per-user"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{login}.json").write_text(json.dumps({
        "timePeriod": {"year": 2026, "month": 6, "day": int(day[-2:])},
        "user": login, "usageItems": items,
    }))


def test_load_weekly_records_reads_and_sums_per_model(tmp_path):
    _write_per_user(tmp_path, "2026-06-01", "alice", [
        {"model": "Opus", "grossQuantity": 100.0, "grossAmount": 1.0},
        {"model": "Opus", "grossQuantity": 20.0, "grossAmount": 0.2},
        {"model": "Haiku", "grossQuantity": 5.0, "grossAmount": 0.05},
    ])
    _write_per_user(tmp_path, "2026-06-01", "empty", [])  # skipped: no usage

    glob_pat = str(tmp_path / "reports" / "*" / "billing" / "per-user" / "*.json")
    records = wpu.load_weekly_records(glob_pat)

    assert len(records) == 1
    rec = records[0]
    assert rec["day"] == "2026-06-01"
    assert rec["user"] == "alice"
    assert rec["credits"] == approx(125.0)
    assert rec["usd"] == approx(1.25)
    assert rec["per_model"] == {"Opus": approx(120.0), "Haiku": approx(5.0)}
