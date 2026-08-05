import json
import re

from flask import session

from app.app import create_app
from app.main.routes import ai_credits as routes


def test_admin_pooled_renders_chart_when_data_present(monkeypatch, fake_source, week_records):
    source = fake_source(week_records)
    monkeypatch.setattr(routes, "get_reports_source", lambda: source)
    app = create_app(False)
    app.config["SECRET_KEY"] = "test_flask"
    client = app.test_client()

    @app.before_request
    def inject_mock_session():
        session["user"] = {
            "userinfo": {
                "https://moj-copilot-ai-credits-dashboard-dev.cloud-platform.service.justice.gov.uk/org_role": "admin"
            }
        }

    resp = client.get("/admin/pooled")
    assert resp.status_code == 200
    assert 'data-chart="pooledTree"' in resp.get_data(as_text=True)


def test_admin_pooled_shows_no_data_message_when_empty(monkeypatch, fake_source):
    monkeypatch.setattr(routes, "get_reports_source", lambda: fake_source([]))
    app = create_app(False)
    app.config["SECRET_KEY"] = "test_flask"
    client = app.test_client()

    @app.before_request
    def inject_mock_session():
        session["user"] = {
            "userinfo": {
                "https://moj-copilot-ai-credits-dashboard-dev.cloud-platform.service.justice.gov.uk/org_role": "admin"
            }
        }

    resp = client.get("/admin/pooled")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'data-chart="pooledTree"' not in body
    assert "No per-user files found" in body


def test_admin_pooled_chart_data_carries_full_date_tooltips(
        monkeypatch, fake_source, week_records, mrows):
    """The embedded chart JSON must carry the full dates the tooltip reads."""
    source = fake_source(week_records, mrows)
    monkeypatch.setattr(routes, "get_reports_source", lambda: source)
    app = create_app(False)
    app.config["SECRET_KEY"] = "test_flask"
    client = app.test_client()

    @app.before_request
    def inject_mock_session():
        session["user"] = {
            "userinfo": {
                "https://moj-copilot-ai-credits-dashboard-dev.cloud-platform.service.justice.gov.uk/org_role": "admin"
            }
        }

    resp = client.get("/admin/pooled?period=monthly&key=2026-06")
    body = resp.get_data(as_text=True)
    spec = json.loads(re.search(
        r'<script type="application/json" id="chart-data">(.*?)</script>',
        body, re.S).group(1))
    for name in ("pooledCumulative", "routedTrend"):
        tips = spec[name]["tooltip_labels"]
        assert tips[0] == "Mon 01 Jun 2026"
        assert len(tips) == len(spec[name]["labels"])


def test_admin_pooled_seats_input_is_sanitised(monkeypatch, fake_source, week_records):
    source = fake_source(week_records)
    monkeypatch.setattr(routes, "get_reports_source", lambda: source)
    app = create_app(False)
    app.config["SECRET_KEY"] = "test_flask"
    client = app.test_client()

    @app.before_request
    def inject_mock_session():
        session["user"] = {
            "userinfo": {
                "https://moj-copilot-ai-credits-dashboard-dev.cloud-platform.service.justice.gov.uk/org_role": "admin"
            }
        }

    probe = "<script>alert(1)</script>"
    resp = client.get(f"/admin/pooled?seats={probe}")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert probe not in body  # raw value must never be reflected
    assert 'name="seats"' in body and 'value="480"' in body  # fell back to default

    # client-side hints on the seats input (server check stays authoritative)
    seats_input = re.search(r'<input[^>]*id="seats"[^>]*>', body).group(0)
    assert 'pattern="[0-9]*"' in seats_input
    assert 'maxlength="4"' in seats_input
