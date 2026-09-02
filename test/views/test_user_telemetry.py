"""Tests for the telemetry block on the My-usage view.

The block is absent whenever the data source serves no telemetry, which is how
the feature stays switched off outside the development deployment.
"""

from app.app import create_app
from app.main.routes import ai_credits as routes
from app.main.services import ai_credits as ac
from app.main.services.reports_source import ReportsSource


class SourceWithTelemetry(ReportsSource):
    def __init__(self, credit_rows, user_rows, activity_rows, available=True):
        self._credit_rows = credit_rows
        self._user_rows = user_rows
        self._activity_rows = activity_rows
        self._available = available

    def model_rows(self):
        return []

    def user_rows(self):
        return self._credit_rows

    def telemetry_available(self):
        return self._available

    def telemetry_user_rows(self, login, start_day, end_day):
        return [r for r in self._user_rows if start_day <= r["day"] <= end_day]

    def telemetry_activity_rows(self, login, start_day, end_day):
        return [r for r in self._activity_rows if start_day <= r["day"] <= end_day]


def _credits(make_record):
    return [make_record("2026-08-04", "alice", 20.0),
            make_record("2026-08-05", "alice", 10.0)]


def _telemetry_day(day):
    return {"day": day, "interactions": 10, "suggested": 40, "accepted": 18,
            "lines_added": 320, "lines_deleted": 40,
            "lines_suggested_added": 200, "has_telemetry": True,
            "review_requested": True, "review_automatic": False}


def _activity(day):
    return {"day": day, "language": "python", "feature": "code_completion",
            "mode": "Inline completion", "suggested": 40, "accepted": 18,
            "lines_added": 320, "lines_suggested_added": 200}


def test_telemetry_absent_when_the_source_has_none(make_record):
    source = SourceWithTelemetry(_credits(make_record), [], [], available=False)
    v = ac.user_view(source, "alice", "$200 / month", "2026-08")
    assert v["telemetry"] is None


def test_telemetry_present_for_the_selected_month(make_record):
    source = SourceWithTelemetry(
        _credits(make_record), [_telemetry_day("2026-08-04")], [_activity("2026-08-04")])
    v = ac.user_view(source, "alice", "$200 / month", "2026-08")
    assert v["telemetry"]["month"] == "2026-08"
    assert v["telemetry"]["volume"]["lines_added"] == 320
    assert v["telemetry"]["languages"][0]["language"] == "Python"


def test_telemetry_follows_the_month_dropdown(make_record):
    """Switching month must change the telemetry, not just the credit charts."""
    credit_rows = _credits(make_record) + [make_record("2026-07-10", "alice", 5.0)]
    source = SourceWithTelemetry(
        credit_rows,
        [_telemetry_day("2026-07-10"), _telemetry_day("2026-08-04")],
        [_activity("2026-07-10"), _activity("2026-08-04")])
    july = ac.user_view(source, "alice", "$200 / month", "2026-07")
    assert july["telemetry"]["month"] == "2026-07"
    assert july["telemetry"]["volume"]["days_recorded"] == 1


def test_telemetry_none_for_a_month_the_person_has_no_rows_in(make_record):
    credit_rows = _credits(make_record) + [make_record("2026-07-10", "alice", 5.0)]
    source = SourceWithTelemetry(
        credit_rows, [_telemetry_day("2026-08-04")], [_activity("2026-08-04")])
    v = ac.user_view(source, "alice", "$200 / month", "2026-07")
    assert v["telemetry"] is None


def test_page_renders_with_telemetry(monkeypatch, make_record):
    """The template must handle the new block without raising.

    Built the way test/routes/test_admin_views.py builds one: there is no
    shared client fixture in this project. Auth0 is already disabled for the
    whole session by test/conftest.py, and the personal page needs no admin
    claim, so no session injection is needed here.
    """
    source = SourceWithTelemetry(
        _credits(make_record), [_telemetry_day("2026-08-04")], [_activity("2026-08-04")])
    monkeypatch.setattr(routes, "get_reports_source", lambda: source)
    app = create_app(False)
    app.config["SECRET_KEY"] = "test_flask"
    response = app.test_client().get("/?user=alice&month=2026-08")
    assert response.status_code == 200


def test_page_renders_without_telemetry(monkeypatch, make_record):
    """The page must be unchanged where the backend serves no telemetry."""
    source = SourceWithTelemetry(_credits(make_record), [], [], available=False)
    monkeypatch.setattr(routes, "get_reports_source", lambda: source)
    app = create_app(False)
    app.config["SECRET_KEY"] = "test_flask"
    response = app.test_client().get("/?user=alice&month=2026-08")
    assert response.status_code == 200
    assert b"What you did in" not in response.data


def _page_text(monkeypatch, source):
    """The rendered page with every run of whitespace collapsed to one space.

    Jinja puts line breaks inside a sentence that is laid out over several
    template lines, so an assertion on the raw HTML would be testing the
    template's indentation rather than its wording.
    """
    monkeypatch.setattr(routes, "get_reports_source", lambda: source)
    app = create_app(False)
    app.config["SECRET_KEY"] = "test_flask"
    response = app.test_client().get("/?user=alice&month=2026-08")
    return " ".join(response.data.decode().split())


def test_summary_sentence_reports_the_acceptance_rate(monkeypatch, make_record):
    """40 offered is above the 20-event minimum, so a rate is shown."""
    source = SourceWithTelemetry(
        _credits(make_record), [_telemetry_day("2026-08-04")],
        [_activity("2026-08-04")])
    page = _page_text(monkeypatch, source)
    assert "Accepted" in page
    assert "45.0%" in page
    assert "of 40 inline completions this month" in page
    assert "mostly in <strong>Python</strong>" in page
    assert "working mostly in <strong>Inline completion</strong>" in page


def test_summary_sentence_says_when_there_are_too_few_to_rate(
        monkeypatch, make_record):
    activity = _activity("2026-08-04")
    activity.update(suggested=5, accepted=2)
    source = SourceWithTelemetry(
        _credits(make_record), [_telemetry_day("2026-08-04")], [activity])
    page = _page_text(monkeypatch, source)
    assert "too few for an acceptance rate" in page


def test_summary_sentence_reports_agent_lines_separately(
        monkeypatch, make_record):
    """Agent edits write code without an accept step, so the sentence must not
    let them look like accepted suggestions."""
    agent = _activity("2026-08-04")
    agent.update(mode="Agent mode", suggested=0, accepted=0, lines_added=13)
    source = SourceWithTelemetry(
        _credits(make_record), [_telemetry_day("2026-08-04")],
        [_activity("2026-08-04"), agent])
    page = _page_text(monkeypatch, source)
    assert "Agent edits wrote <strong>13</strong> lines into files" in page


def test_every_tile_is_rendered(monkeypatch, make_record):
    source = SourceWithTelemetry(
        _credits(make_record), [_telemetry_day("2026-08-04")],
        [_activity("2026-08-04")])
    page = _page_text(monkeypatch, source)
    for label in ("Inline completion acceptance rate",
                  "Inline completion lines kept",
                  "Lines of code applied",
                  "Activity across all modes",
                  "Active days",
                  "Top mode",
                  "Chats and prompts started"):
        assert label in page


def test_no_lines_kept_rate_when_more_lines_were_kept_than_suggested(
        monkeypatch, make_record):
    """The fixture day added 320 lines against 200 suggested, which cannot be
    a percentage. The tile must say why rather than print a rate over 100%."""
    source = SourceWithTelemetry(
        _credits(make_record), [_telemetry_day("2026-08-04")],
        [_activity("2026-08-04")])
    page = _page_text(monkeypatch, source)
    assert "more lines than the 200 suggested" in page
