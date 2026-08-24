"""Smoke tests for the admin daily/weekly pages on the new parquet source."""

from flask import session

from app.app import create_app
from app.main.routes import ai_credits as routes

_ADMIN_CLAIM = ("https://moj-copilot-ai-credits-dashboard-dev.cloud-platform."
                "service.justice.gov.uk/org_role")


def _admin_client(monkeypatch, source):
    monkeypatch.setattr(routes, "get_reports_source", lambda: source)
    app = create_app(False)
    app.config["SECRET_KEY"] = "test_flask"
    client = app.test_client()

    @app.before_request
    def inject_mock_session():  # pylint: disable=unused-variable
        session["user"] = {"userinfo": {_ADMIN_CLAIM: "admin"}}

    return client


def _user_rows():
    return [{"day": "2026-06-01", "user_login": "alice", "credits": 60.0},
            {"day": "2026-06-01", "user_login": "bob", "credits": 40.0}]


def test_admin_index_redirects_to_pooled(monkeypatch, fake_source):
    client = _admin_client(monkeypatch, fake_source([], model_rows=[]))
    resp = client.get("/admin")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/pooled")


def test_admin_daily_renders_family_and_routed(monkeypatch, fake_source,
                                               model_records):
    source = fake_source(_user_rows(), model_rows=model_records)
    client = _admin_client(monkeypatch, source)
    resp = client.get("/admin/daily")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "By model family" in body
    assert 'data-chart="family"' in body
    assert 'data-chart="routed"' in body
    assert "Week-to-date" in body


def test_admin_daily_no_data(monkeypatch, fake_source):
    client = _admin_client(monkeypatch, fake_source([], model_rows=[]))
    resp = client.get("/admin/daily")
    assert resp.status_code == 200
    assert "No data found" in resp.get_data(as_text=True)


def test_admin_weekly_renders_table_without_top_model(monkeypatch, fake_source):
    source = fake_source(_user_rows())
    client = _admin_client(monkeypatch, source)
    resp = client.get("/admin/weekly")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Top model" not in body
    assert 'data-chart="topUsers"' in body


def test_admin_pages_keep_the_70_and_39_budgets(monkeypatch, fake_source,
                                                model_records):
    """The $200 budget belongs to My Usage only; admin stays on $70/$39."""
    source = fake_source(_user_rows(), model_rows=model_records)
    client = _admin_client(monkeypatch, source)
    for path in ("/admin/weekly", "/admin/pooled"):
        body = client.get(path).get_data(as_text=True)
        assert '$70 / month" selected' in body, path
        assert "$39 / month" in body, path
        assert "$200 / month" not in body, path


def test_admin_pooled_renders_routed_trend(monkeypatch, fake_source,
                                           model_records):
    source = fake_source(_user_rows(), model_rows=model_records)
    client = _admin_client(monkeypatch, source)
    resp = client.get("/admin/pooled")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Auto-routed vs explicitly chosen" in body
    assert 'data-chart="routedTrend"' in body


def test_admin_pooled_hides_routed_trend_without_model_rows(monkeypatch,
                                                            fake_source):
    source = fake_source(_user_rows(), model_rows=[])
    client = _admin_client(monkeypatch, source)
    resp = client.get("/admin/pooled")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'data-chart="routedTrend"' not in body
    assert "Auto-routed vs explicitly chosen" not in body
