from app.main.services import ai_credits as ac


def _records(make_record):
    return [
        make_record("2026-06-01", "alice", 10.0),
        make_record("2026-06-08", "alice", 5.0),
    ]


def test_weekly_view_exposes_week_ranges(fake_source, make_record):
    view = ac.weekly_view(
        fake_source(_records(make_record)), plan=None, week="2026-W23"
    )
    assert view["week_ranges"]["2026-W23"] == "1–7 Jun"
    assert view["week_ranges"]["2026-W24"] == "8–14 Jun"


def test_user_view_exposes_week_ranges_and_chart_labels(fake_source, make_record):
    view = ac.user_view(fake_source(_records(make_record)), login="alice", plan=None)
    assert view["week_ranges"]["2026-W23"] == "1–7 Jun"
    assert view["weekly_chart"]["labels"] == [
        "2026-W23 (1–7 Jun)",
        "2026-W24 (8–14 Jun)",
    ]
