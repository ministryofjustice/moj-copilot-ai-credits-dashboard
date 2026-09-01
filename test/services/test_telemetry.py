"""Tests for the telemetry calculation module.

Everything here works on plain dictionaries, with no database and no files,
because that is the point of keeping the arithmetic in its own module.

Two rules the pipeline documentation imposes are asserted directly:
nulls are not zeros, and no rate is computed across all features.
"""

from app.main.services import telemetry as tel


def _day(day, **overrides):
    row = {
        "day": day, "interactions": 10, "suggested": 40, "accepted": 18,
        "lines_added": 320, "lines_deleted": 40, "lines_suggested_added": 200,
        "has_telemetry": True, "review_requested": False,
        "review_automatic": False,
    }
    row.update(overrides)
    return row


def test_volume_sums_every_count_across_the_month():
    rows = [_day("2026-08-01"), _day("2026-08-02")]
    v = tel.volume(rows)
    assert v["interactions"] == 20
    assert v["suggested"] == 80
    assert v["accepted"] == 36
    assert v["lines_added"] == 640
    assert v["lines_deleted"] == 80


def test_volume_counts_days_with_and_without_telemetry():
    """About a quarter of person-day records arrive with no activity data.
    A month total that does not say how many days it covers under-reports."""
    rows = [_day("2026-08-01"), _day("2026-08-02", has_telemetry=False)]
    v = tel.volume(rows)
    assert v["days_recorded"] == 2
    assert v["days_with_telemetry"] == 1


def test_volume_treats_a_null_count_as_absent_not_zero():
    """A null contributes nothing to the sum but must not make the day look
    like a day of zero activity."""
    rows = [_day("2026-08-01", suggested=None, interactions=None),
            _day("2026-08-02")]
    v = tel.volume(rows)
    assert v["suggested"] == 40
    assert v["interactions"] == 10


def test_volume_of_an_empty_month_is_all_zeros():
    v = tel.volume([])
    assert v == {"interactions": 0, "suggested": 0, "accepted": 0,
                 "lines_added": 0, "lines_deleted": 0,
                 "days_recorded": 0, "days_with_telemetry": 0}


def test_review_activity_counts_days_of_each_kind():
    rows = [
        _day("2026-08-01", review_requested=True, review_automatic=False),
        _day("2026-08-02", review_requested=True, review_automatic=True),
        _day("2026-08-03", review_requested=False, review_automatic=True),
    ]
    r = tel.review_activity(rows)
    assert r["requested"] == 2
    assert r["automatic"] == 2
    assert r["days_recorded"] == 3


def test_review_activity_does_not_count_a_null_as_a_false():
    """Null means no telemetry arrived. Counting it as 'no review happened'
    would assert something the data does not say. Real August data has days
    where the review flags are null even though other telemetry arrived."""
    rows = [_day("2026-08-01", review_requested=None, review_automatic=None,
                 has_telemetry=False),
            _day("2026-08-02", review_requested=True, review_automatic=False)]
    r = tel.review_activity(rows)
    assert r["requested"] == 1
    assert r["automatic"] == 0
    assert r["days_without_telemetry"] == 1


def test_review_activity_of_an_empty_month():
    assert tel.review_activity([]) == {
        "requested": 0, "automatic": 0, "days_recorded": 0,
        "days_without_telemetry": 0}


def _act(language, mode, **overrides):
    row = {"day": "2026-08-01", "language": language, "feature": "code_completion",
           "mode": mode, "suggested": 10, "accepted": 4,
           "lines_added": 100, "lines_suggested_added": 80}
    row.update(overrides)
    return row


def test_mode_split_groups_and_ranks_by_suggestions():
    rows = [
        _act("python", "Inline completion", suggested=10, lines_added=100),
        _act("python", "Inline completion", suggested=5, lines_added=50),
        _act("go", "Agent mode", suggested=30, lines_added=900),
    ]
    modes = tel.mode_split(rows)
    assert [m["mode"] for m in modes] == ["Agent mode", "Inline completion"]
    assert modes[0]["suggested"] == 30
    assert modes[0]["lines_added"] == 900
    assert modes[1]["suggested"] == 15
    assert modes[1]["lines_added"] == 150


def test_mode_split_share_is_a_fraction_of_all_suggestions():
    rows = [_act("python", "Chat", suggested=30),
            _act("go", "CLI", suggested=10)]
    modes = tel.mode_split(rows)
    assert modes[0]["share"] == 0.75
    assert modes[1]["share"] == 0.25


def test_mode_split_share_is_zero_when_nothing_was_suggested():
    """Agent-heavy months can legitimately record no suggestions. Dividing by
    that total must not raise."""
    rows = [_act("python", "Agent mode", suggested=0, lines_added=500)]
    modes = tel.mode_split(rows)
    assert modes[0]["share"] == 0.0
    assert modes[0]["lines_added"] == 500


def test_mode_split_reports_no_acceptance_figure():
    """Acceptance per mode is deliberately absent: agent features apply code
    without a discrete accept step, so the number would mislead."""
    modes = tel.mode_split([_act("python", "Agent mode")])
    assert "accepted" not in modes[0]


def test_mode_split_skips_null_counts():
    rows = [_act("python", "Chat", suggested=None, lines_added=None),
            _act("go", "Chat", suggested=10, lines_added=100)]
    modes = tel.mode_split(rows)
    assert modes[0]["suggested"] == 10
    assert modes[0]["lines_added"] == 100


def test_mode_split_of_no_rows_is_empty():
    assert tel.mode_split([]) == []
