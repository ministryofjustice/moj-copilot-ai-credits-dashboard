"""Tests for the org telemetry calculations.

Plain dictionaries only. The rules from telemetry.py are asserted again here
because this module applies them to everyone at once: nulls are not zeros,
and the only acceptance rate is inline completion's.
"""

import json

import pytest

from app.main.services import org_telemetry as org


def _person_day(login, day="2026-08-03", **overrides):
    row = {
        "day": day, "user_login": login,
        "interactions": 0, "suggested": 0, "accepted": 0,
        "lines_added": 0, "lines_deleted": 0, "lines_suggested_added": 0,
        "has_telemetry": True, "review_requested": False,
        "review_automatic": False, "credits": 0.0,
        "used_chat": False, "used_agent": False, "used_cli": False,
        "used_app": False, "used_coding_agent": False,
        "used_cloud_agent": False,
        "cli_requests": None, "app_requests": None,
        "cli_prompts": None, "app_prompts": None,
    }
    row.update(overrides)
    return row


def _activity(login, language, mode, day="2026-08-03", **overrides):
    row = {
        "day": day, "user_login": login, "language": language,
        "feature": "any", "mode": mode,
        "suggested": 0, "accepted": 0,
        "lines_added": 0, "lines_suggested_added": 0,
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------- active days
def test_a_person_day_with_nothing_set_is_not_active():
    assert org.is_active(_person_day("a")) is False


@pytest.mark.parametrize("overrides", [
    {"interactions": 1}, {"suggested": 1}, {"credits": 0.5},
    {"used_chat": True}, {"used_agent": True}, {"used_cli": True},
    {"used_app": True}, {"used_coding_agent": True},
    {"used_cloud_agent": True}, {"review_requested": True},
    {"review_automatic": True},
])
def test_any_one_signal_makes_a_person_day_active(overrides):
    assert org.is_active(_person_day("a", **overrides)) is True


def test_a_reduced_record_is_not_active():
    """GitHub sends nulls on some days. That is not evidence of use."""
    row = _person_day("a", interactions=None, suggested=None, credits=None,
                      has_telemetry=False, used_chat=None,
                      review_requested=None)
    assert org.is_active(row) is False


# ---------------------------------------------------------------------- tiles
def test_people_active_counts_distinct_active_logins_against_seats_seen():
    rows = [_person_day("a", suggested=5),
            _person_day("a", day="2026-08-04", suggested=5),
            _person_day("b")]
    t = org.tiles(rows, [])
    assert t["people_active"] == 1
    assert t["seats_seen"] == 2


def test_days_covered_reports_first_and_last_day():
    rows = [_person_day("a", day="2026-08-05"),
            _person_day("a", day="2026-08-01"),
            _person_day("b", day="2026-08-05")]
    t = org.tiles(rows, [])
    assert (t["days"], t["first_day"], t["last_day"]) == (
        2, "2026-08-01", "2026-08-05")


def test_totals_skip_nulls():
    rows = [_person_day("a", suggested=10, interactions=3, lines_added=7),
            _person_day("b", suggested=None, interactions=None,
                        lines_added=None)]
    t = org.tiles(rows, [])
    assert (t["suggested"], t["interactions"], t["lines_added"]) == (10, 3, 7)


def test_inline_tiles_use_inline_completion_only():
    activity = [
        _activity("a", "python", "Inline completion", suggested=30,
                  accepted=12, lines_added=50, lines_suggested_added=100),
        _activity("a", "python", "Agent mode", suggested=500, accepted=1,
                  lines_added=900),
    ]
    t = org.tiles([_person_day("a")], activity)
    assert t["inline_suggested"] == 30
    assert t["inline_accepted"] == 12
    assert t["inline_acceptance_rate"] == pytest.approx(0.4)
    assert t["inline_lines_kept"] == 50
    assert t["inline_lines_suggested"] == 100
    assert t["inline_keep_rate"] == pytest.approx(0.5)
    assert t["agent_lines_added"] == 900


def test_inline_rate_is_none_below_the_minimum():
    activity = [_activity("a", "python", "Inline completion",
                          suggested=19, accepted=10)]
    assert org.tiles([_person_day("a")], activity)["inline_acceptance_rate"] is None


def test_requests_and_prompts_add_cli_and_app_skipping_nulls():
    rows = [_person_day("a", cli_requests=4, app_requests=None,
                        cli_prompts=2, app_prompts=1),
            _person_day("b", cli_requests=None, app_requests=6)]
    t = org.tiles(rows, [])
    assert (t["requests"], t["prompts"]) == (10, 3)


def test_languages_seen_folds_aliases_and_drops_non_languages():
    activity = [
        _activity("a", "ts", "Inline completion", accepted=5),
        _activity("a", "typescript", "Inline completion", accepted=5),
        _activity("a", "python", "Inline completion", accepted=4),
        _activity("a", "unknown", "Inline completion", accepted=99),
    ]
    t = org.tiles([_person_day("a")], activity)
    assert t["languages_seen"] == 2
    assert t["top_language"] == "TypeScript"


def test_tiles_on_empty_rows_do_not_fail():
    t = org.tiles([], [])
    assert t["days"] == 0
    assert t["first_day"] is None
    assert t["top_language"] is None


# ---------------------------------------------------------- capability share
def test_capability_share_is_a_percentage_of_that_days_active_people():
    rows = [_person_day("a", suggested=1, used_chat=True),
            _person_day("b", suggested=1),
            _person_day("c", suggested=1),
            _person_day("d", suggested=1, used_chat=True,
                        review_requested=True),
            _person_day("e")]  # not active: left out of the denominator
    share = org.capability_share(rows, ["2026-08-03"])
    by_label = {s["label"]: s["data"] for s in share["series"]}
    assert by_label["Chat"] == [50.0]
    assert by_label["Code review requested"] == [25.0]
    assert by_label["Agent mode"] == [0.0]
    assert [s["label"] for s in share["series"]] == [
        "Chat", "Agent mode", "Copilot CLI", "Coding agent",
        "Code review requested"]


def test_capability_share_is_none_on_a_day_with_no_active_people():
    share = org.capability_share([_person_day("a")], ["2026-08-03"])
    assert all(s["data"] == [None] for s in share["series"])


def test_capability_share_axis_uses_day_numbers_and_full_dates():
    share = org.capability_share([], ["2026-08-03"])
    assert share["labels"] == ["3"]
    assert share["tooltip_labels"] == ["Mon 03 Aug 2026"]


# ----------------------------------------------------------------------- view
def test_view_when_telemetry_is_not_configured(org_source):
    assert org.org_telemetry_view(org_source(available=False), None) == {
        "available": False}


def test_view_when_there_is_no_telemetry_yet(org_source):
    assert org.org_telemetry_view(org_source(), None) == {
        "available": True, "has_data": False}


def test_view_defaults_to_the_latest_month(org_source):
    source = org_source([_person_day("a", day="2026-07-30", suggested=1),
                         _person_day("a", day="2026-08-03", suggested=1)])
    v = org.org_telemetry_view(source, None)
    assert v["month"] == "2026-08"
    assert v["month_label"] == "Aug 2026"
    assert v["months"] == [{"value": "2026-07", "text": "Jul 2026"},
                           {"value": "2026-08", "text": "Aug 2026"}]
    assert v["tiles"]["days"] == 1


def test_view_follows_the_chosen_month(org_source):
    source = org_source([_person_day("a", day="2026-07-30", suggested=1),
                         _person_day("a", day="2026-08-03", suggested=1)])
    v = org.org_telemetry_view(source, "2026-07")
    assert v["month"] == "2026-07"
    assert v["tiles"]["first_day"] == "2026-07-30"


def test_view_ignores_a_month_it_does_not_have(org_source):
    source = org_source([_person_day("a", day="2026-08-03", suggested=1)])
    assert org.org_telemetry_view(source, "1999-01' OR 1=1")["month"] == "2026-08"


def test_view_contains_no_login(org_source):
    source = org_source(
        [_person_day("zz-secret-login", suggested=1, used_chat=True)],
        [_activity("zz-secret-login", "python", "Inline completion",
                   suggested=30, accepted=10)])
    v = org.org_telemetry_view(source, None)
    assert "zz-secret-login" not in json.dumps(v)


# --------------------------------------------------------- activity per day
DAYS = ["2026-08-01", "2026-08-03"]  # a Saturday and a Monday


def test_daily_activity_sums_each_day_skipping_nulls():
    rows = [_person_day("a", day="2026-08-01", suggested=4, accepted=2,
                        interactions=1),
            _person_day("b", day="2026-08-01", suggested=None, accepted=None,
                        interactions=None),
            _person_day("a", day="2026-08-03", suggested=10, accepted=3,
                        interactions=5)]
    d = org.daily_activity(rows, DAYS)
    assert d["suggested"] == [4, 10]
    assert d["accepted"] == [2, 3]
    assert d["interactions"] == [1, 5]
    assert d["labels"] == ["1", "3"]


def test_daily_inline_rate_uses_inline_completion_only():
    activity = [
        _activity("a", "python", "Inline completion", day="2026-08-03",
                  suggested=40, accepted=10),
        _activity("a", "python", "Agent mode", day="2026-08-03",
                  suggested=400, accepted=0),
    ]
    assert org.daily_inline_rate(activity, DAYS)["rates"] == [None, 25.0]


def test_daily_inline_rate_is_none_below_the_minimum():
    activity = [_activity("a", "python", "Inline completion",
                          day="2026-08-03", suggested=19, accepted=19)]
    assert org.daily_inline_rate(activity, DAYS)["rates"] == [None, None]


def test_daily_people_counts_active_people_and_marks_weekends():
    rows = [_person_day("a", day="2026-08-01", suggested=1),
            _person_day("a", day="2026-08-03", suggested=1),
            _person_day("b", day="2026-08-03", used_chat=True),
            _person_day("c", day="2026-08-03")]  # not active
    d = org.daily_people(rows, DAYS)
    assert d["people"] == [1, 2]
    assert d["weekend"] == [True, False]


def test_daily_lines_keeps_suggested_and_applied_separate():
    rows = [_person_day("a", day="2026-08-03", lines_suggested_added=10,
                        lines_added=30)]
    d = org.daily_lines(rows, DAYS)
    assert d["lines_suggested"] == [0, 10]
    assert d["lines_added"] == [0, 30]


def test_view_includes_the_daily_series(org_source):
    v = org.org_telemetry_view(
        org_source([_person_day("a", suggested=1)]), None)
    for key in ("daily_activity", "daily_inline_rate", "daily_people",
                "daily_lines"):
        assert v[key]["labels"] == ["3"]


# ------------------------------------------------------------------ languages
def test_language_chart_ranks_by_accepted_and_keeps_fifteen():
    activity = [_activity("a", f"lang{i:02d}", "Inline completion",
                          suggested=100, accepted=i) for i in range(20)]
    g = org.language_chart(activity)
    assert len(g["labels"]) == 15
    assert g["labels"][0] == "lang19"
    assert g["accepted"][0] == 19


def test_language_chart_folds_aliases():
    activity = [_activity("a", "ts", "Inline completion", accepted=2,
                          suggested=5, lines_added=7),
                _activity("b", "typescript", "Agent mode", accepted=1,
                          suggested=5, lines_added=3)]
    g = org.language_chart(activity)
    assert g["labels"] == ["TypeScript"]
    assert (g["suggested"], g["accepted"], g["lines_added"]) == ([10], [3], [10])


def test_language_inline_rate_uses_inline_completion_only():
    activity = [_activity("a", "python", "Inline completion",
                          suggested=40, accepted=10),
                _activity("a", "python", "Agent mode",
                          suggested=400, accepted=390)]
    assert org.language_chart(activity)["inline_rates"] == [25.0]


def test_language_inline_rate_is_none_without_enough_inline_use():
    activity = [_activity("a", "go", "Agent mode", suggested=400, accepted=9),
                _activity("a", "rust", "Inline completion", suggested=5,
                          accepted=1)]
    assert org.language_chart(activity)["inline_rates"] == [None, None]


def test_view_includes_the_language_series(org_source):
    v = org.org_telemetry_view(org_source(
        [_person_day("a", suggested=1)],
        [_activity("a", "python", "Inline completion", accepted=1)]), None)
    assert v["languages"]["labels"] == ["Python"]


def test_language_chart_uses_the_personal_page_names():
    """The org page folds language names with the same mapping as My Usage."""
    activity = [_activity("a", raw, "Inline completion", accepted=1)
                for raw in ("cs", "csharp", "C#", "ts", "tsx", "typescript")]
    g = org.language_chart(activity)
    assert dict(zip(g["labels"], g["accepted"])) == {"C#": 3, "TypeScript": 3}


# ---------------------------------------------------------------------- modes
def test_mode_chart_orders_modes_by_suggestions():
    activity = [_activity("a", "python", "Chat", suggested=5, accepted=1),
                _activity("a", "python", "Inline completion", suggested=50,
                          accepted=20),
                _activity("b", "go", "Inline completion", suggested=10,
                          accepted=2)]
    m = org.mode_chart(activity)
    assert m["labels"] == ["Inline completion", "Chat"]
    assert m["suggested"] == [60, 5]
    assert m["accepted"] == [22, 1]


def test_mode_chart_counts_a_person_once_per_mode_they_used():
    activity = [_activity("a", "python", "Agent mode", lines_added=10),
                _activity("a", "go", "Agent mode", lines_added=5),
                _activity("a", "python", "Chat", suggested=1),
                _activity("b", "python", "Agent mode", suggested=3),
                _activity("c", "python", "Chat")]  # all zero: not counted
    m = org.mode_chart(activity)
    people = dict(zip(m["labels"], m["people"]))
    assert people == {"Agent mode": 2, "Chat": 1}


def test_view_includes_the_mode_series(org_source):
    v = org.org_telemetry_view(org_source(
        [_person_day("a", suggested=1)],
        [_activity("a", "python", "Chat", suggested=1)]), None)
    assert v["modes"]["labels"] == ["Chat"]
