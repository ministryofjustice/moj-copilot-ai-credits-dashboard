"""Tests for the telemetry calculation module.

Everything here works on plain dictionaries, with no database and no files,
because that is the point of keeping the arithmetic in its own module.

Two rules the pipeline documentation imposes are asserted directly:
nulls are not zeros, and no rate is computed across all features.
"""

from app.main.services import telemetry as tel
from app.main.services.reports_source import ReportsSource


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


def test_language_aliases_are_folded_together():
    """Both spellings occur in the real August data."""
    rows = [_act("csharp", "Inline completion", lines_added=100),
            _act("c#", "Chat", lines_added=50),
            _act("python", "Inline completion", lines_added=30)]
    languages = tel.top_languages(rows)
    assert [lang["language"] for lang in languages] == ["C#", "Python"]
    assert languages[0]["lines_added"] == 150


def test_shell_spellings_are_folded_together():
    rows = [_act("shell", "CLI", lines_added=10),
            _act("shellscript", "CLI", lines_added=10),
            _act("bash", "CLI", lines_added=10),
            _act("sh", "CLI", lines_added=10)]
    languages = tel.top_languages(rows)
    assert [lang["language"] for lang in languages] == ["Shell"]
    assert languages[0]["lines_added"] == 40


def test_terraform_spellings_are_folded_together():
    rows = [_act("terraform", "Chat", lines_added=10),
            _act("hcl", "Chat", lines_added=10),
            _act("tf", "Chat", lines_added=10),
            _act("terraform-vars", "Chat", lines_added=10)]
    assert tel.top_languages(rows)[0] == {
        "language": "Terraform", "suggested": 40, "lines_added": 40}


def test_single_letter_language_is_given_its_real_name():
    assert tel.top_languages([_act("r", "Chat")])[0]["language"] == "R"


def test_unknown_languages_are_kept_under_their_own_name():
    languages = tel.top_languages([_act("nim", "Chat", lines_added=10)])
    assert languages[0]["language"] == "nim"


def test_non_language_values_are_excluded_from_the_ranking():
    """`unknown` alone is the seventh largest value in the real August data.
    Ranking it beside Python would misdescribe what the person wrote."""
    rows = [_act("python", "Chat", lines_added=100),
            _act("unknown", "Chat", lines_added=500),
            _act("plaintext", "Chat", lines_added=400),
            _act("text", "Chat", lines_added=300),
            _act("others", "Chat", lines_added=300),
            _act("prompt", "Chat", lines_added=200),
            _act("instructions", "Chat", lines_added=100),
            _act("skill", "Chat", lines_added=100),
            _act("chatagent", "Chat", lines_added=100)]
    languages = tel.top_languages(rows)
    assert [lang["language"] for lang in languages] == ["Python"]


def test_lines_not_attributed_to_a_language_are_reported_separately():
    rows = [_act("python", "Chat", lines_added=100),
            _act("unknown", "Chat", lines_added=500)]
    assert tel.unattributed_lines(rows) == 500


def test_unattributed_lines_skips_nulls():
    assert tel.unattributed_lines([_act("unknown", "Chat", lines_added=None)]) == 0


def test_languages_beyond_the_limit_are_grouped_as_other():
    rows = [_act(f"lang{i}", "Chat", lines_added=100 - i) for i in range(10)]
    languages = tel.top_languages(rows, limit=3)
    assert [lang["language"] for lang in languages[:3]] == ["lang0", "lang1", "lang2"]
    assert languages[3]["language"] == "Other"
    # The remaining seven: 97 + 96 + 95 + 94 + 93 + 92 + 91
    assert languages[3]["lines_added"] == 658


def test_no_other_row_when_nothing_is_left_over():
    rows = [_act("python", "Chat", lines_added=10)]
    assert [lang["language"] for lang in tel.top_languages(rows, limit=3)] == ["Python"]


def test_top_languages_of_no_rows_is_empty():
    assert tel.top_languages([]) == []


class StubTelemetrySource(ReportsSource):
    """Serves fixed telemetry and records the day range it was asked for."""

    def __init__(self, user_rows=None, activity_rows=None, available=True):
        self._user_rows = list(user_rows or [])
        self._activity_rows = list(activity_rows or [])
        self._available = available
        self.ranges = []

    def model_rows(self):
        return []

    def user_rows(self):
        return []

    def telemetry_available(self):
        return self._available

    def telemetry_user_rows(self, login, start_day, end_day):
        self.ranges.append((login, start_day, end_day))
        return self._user_rows

    def telemetry_activity_rows(self, login, start_day, end_day):
        self.ranges.append((login, start_day, end_day))
        return self._activity_rows


def test_view_is_none_when_the_backend_has_no_telemetry():
    """This is the whole development-only gate: no tables, no section."""
    source = StubTelemetrySource([_day("2026-08-01")], available=False)
    assert tel.telemetry_view(source, "alice", "2026-08") is None


def test_view_is_none_when_the_person_has_no_rows():
    assert tel.telemetry_view(StubTelemetrySource(), "alice", "2026-08") is None


def test_view_asks_for_the_whole_selected_month():
    source = StubTelemetrySource([_day("2026-08-01")])
    tel.telemetry_view(source, "alice", "2026-08")
    assert source.ranges[0] == ("alice", "2026-08-01", "2026-08-31")


def test_view_handles_a_thirty_day_month():
    source = StubTelemetrySource([_day("2026-09-01")])
    tel.telemetry_view(source, "alice", "2026-09")
    assert source.ranges[0] == ("alice", "2026-09-01", "2026-09-30")


def test_view_handles_february_in_a_leap_year():
    source = StubTelemetrySource([_day("2028-02-01")])
    tel.telemetry_view(source, "alice", "2028-02")
    assert source.ranges[0] == ("alice", "2028-02-01", "2028-02-29")


def test_view_carries_every_section():
    source = StubTelemetrySource(
        user_rows=[_day("2026-08-01", review_requested=True)],
        activity_rows=[_act("python", "Chat", lines_added=100),
                       _act("unknown", "Chat", lines_added=25)],
    )
    view = tel.telemetry_view(source, "alice", "2026-08")
    assert view["month"] == "2026-08"
    assert view["volume"]["suggested"] == 40
    assert view["review"]["requested"] == 1
    assert view["modes"][0]["mode"] == "Chat"
    assert view["languages"][0]["language"] == "Python"
    assert view["unattributed_lines_added"] == 25


def test_view_survives_a_person_with_days_but_no_language_rows():
    """The pipeline documentation records that code review, the coding agent
    and the cloud agent produce no language rows at all."""
    source = StubTelemetrySource(user_rows=[_day("2026-08-01")], activity_rows=[])
    view = tel.telemetry_view(source, "alice", "2026-08")
    assert view is not None
    assert view["modes"] == []
    assert view["languages"] == []
    assert view["unattributed_lines_added"] == 0


# ---------------------------------------------------------- inline completion
def test_inline_completion_totals_only_that_mode():
    """The acceptance figures on the page describe inline completion alone.
    Agent and chat features apply code without a discrete accept step, so
    folding them in would drag the rate towards zero for no real reason."""
    rows = [
        _act("python", "Inline completion", suggested=30, accepted=12,
             lines_added=200, lines_suggested_added=600),
        _act("go", "Inline completion", suggested=10, accepted=3,
             lines_added=50, lines_suggested_added=150),
        _act("go", "Agent mode", suggested=900, accepted=1,
             lines_added=9000, lines_suggested_added=9000),
    ]
    inline = tel.inline_completion(rows)
    assert inline["suggested"] == 40
    assert inline["accepted"] == 15
    assert inline["lines_added"] == 250
    assert inline["lines_suggested_added"] == 750


def test_inline_completion_acceptance_rate_is_a_fraction():
    rows = [_act("python", "Inline completion", suggested=40, accepted=10)]
    assert tel.inline_completion(rows)["acceptance_rate"] == 0.25


def test_no_acceptance_rate_below_the_minimum_count():
    """A rate over a handful of completions is noise, not a measurement."""
    rows = [_act("python", "Inline completion", suggested=19, accepted=10)]
    assert tel.inline_completion(rows)["acceptance_rate"] is None


def test_acceptance_rate_appears_exactly_at_the_minimum_count():
    rows = [_act("python", "Inline completion", suggested=20, accepted=5)]
    assert tel.inline_completion(rows)["acceptance_rate"] == 0.25


def test_no_acceptance_rate_when_more_were_accepted_than_offered():
    """GitHub has been observed reporting this. A rate above 100 per cent is
    not a fact about the person, so no rate is shown at all."""
    rows = [_act("python", "Inline completion", suggested=40, accepted=41)]
    assert tel.inline_completion(rows)["acceptance_rate"] is None


def test_inline_completion_lines_kept_rate():
    rows = [_act("python", "Inline completion",
                 lines_added=250, lines_suggested_added=1000)]
    assert tel.inline_completion(rows)["lines_kept_rate"] == 0.25


def test_no_lines_kept_rate_below_the_minimum_count():
    rows = [_act("python", "Inline completion",
                 lines_added=5, lines_suggested_added=19)]
    assert tel.inline_completion(rows)["lines_kept_rate"] is None


def test_no_lines_kept_rate_when_more_were_kept_than_suggested():
    """GitHub leaves agent edits out of the suggested-lines column but counts
    them in lines added, so this pair can exceed 100 per cent."""
    rows = [_act("python", "Inline completion",
                 lines_added=900, lines_suggested_added=100)]
    assert tel.inline_completion(rows)["lines_kept_rate"] is None


def test_inline_completion_skips_null_counts():
    rows = [_act("python", "Inline completion", suggested=None, accepted=None,
                 lines_added=None, lines_suggested_added=None),
            _act("go", "Inline completion", suggested=30, accepted=9,
                 lines_added=100, lines_suggested_added=400)]
    inline = tel.inline_completion(rows)
    assert inline["suggested"] == 30
    assert inline["accepted"] == 9
    assert inline["acceptance_rate"] == 0.3


def test_inline_completion_of_no_rows_is_zeros_and_no_rates():
    inline = tel.inline_completion([])
    assert inline == {"suggested": 0, "accepted": 0, "lines_added": 0,
                      "lines_suggested_added": 0, "acceptance_rate": None,
                      "lines_kept_rate": None}


def test_inline_completion_when_the_person_used_only_agents():
    inline = tel.inline_completion([_act("go", "Agent mode", suggested=500)])
    assert inline["suggested"] == 0
    assert inline["acceptance_rate"] is None


# --------------------------------------------------------------- agent lines
def test_agent_lines_added_counts_only_agent_mode():
    """Agent edits write code into files without an accept step, so these
    lines are reported separately from accepted suggestions."""
    rows = [_act("go", "Agent mode", lines_added=900),
            _act("go", "Agent mode", lines_added=100),
            _act("python", "Inline completion", lines_added=50)]
    assert tel.agent_lines_added(rows) == 1000


def test_agent_lines_added_skips_nulls():
    rows = [_act("go", "Agent mode", lines_added=None),
            _act("go", "Agent mode", lines_added=7)]
    assert tel.agent_lines_added(rows) == 7


def test_agent_lines_added_of_no_rows_is_zero():
    assert tel.agent_lines_added([]) == 0


# ------------------------------------------------------------------ headline
def test_headline_carries_the_parts_of_the_summary_sentence():
    rows = [
        _act("ruby", "Inline completion", suggested=40, accepted=10,
             lines_added=900, lines_suggested_added=1000),
        _act("go", "Agent mode", suggested=5, accepted=0, lines_added=13,
             lines_suggested_added=0),
    ]
    head = tel.headline(tel.inline_completion(rows), tel.mode_split(rows),
                        tel.top_languages(rows), tel.agent_lines_added(rows))
    assert head["acceptance_rate"] == 0.25
    assert head["inline_suggested"] == 40
    assert head["top_language"] == "Ruby"
    assert head["top_mode"] == "Inline completion"
    assert head["agent_lines_added"] == 13


def test_headline_leaves_out_what_was_never_recorded():
    """Someone with days recorded but no language or mode rows still gets a
    sentence; the missing parts are left out rather than guessed."""
    head = tel.headline(tel.inline_completion([]), [], [], 0)
    assert head["acceptance_rate"] is None
    assert head["inline_suggested"] == 0
    assert head["top_language"] is None
    assert head["top_mode"] is None
    assert head["agent_lines_added"] == 0


# ------------------------------------------------------------- top languages
def test_top_languages_shows_five_by_default():
    rows = [_act(f"lang{i}", "Chat", lines_added=100 - i) for i in range(8)]
    languages = tel.top_languages(rows)
    assert [lang["language"] for lang in languages[:5]] == [
        "lang0", "lang1", "lang2", "lang3", "lang4"]
    assert languages[5]["language"] == "Other"
    assert len(languages) == 6


# ------------------------------------------------------------------ the view
def test_view_carries_the_headline_and_inline_figures():
    source = StubTelemetrySource(
        user_rows=[_day("2026-08-01")],
        activity_rows=[_act("ruby", "Inline completion", suggested=40,
                            accepted=10, lines_added=200,
                            lines_suggested_added=800),
                       _act("go", "Agent mode", lines_added=13)],
    )
    view = tel.telemetry_view(source, "alice", "2026-08")
    assert view["inline"]["acceptance_rate"] == 0.25
    assert view["inline"]["lines_kept_rate"] == 0.25
    assert view["agent_lines_added"] == 13
    assert view["headline"]["top_language"] == "Ruby"
