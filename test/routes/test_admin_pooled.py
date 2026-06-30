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
