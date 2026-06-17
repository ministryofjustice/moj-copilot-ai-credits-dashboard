from app.app import create_app
from app.main.routes import ai_credits as routes


def test_admin_pooled_renders_chart_when_data_present(monkeypatch, fake_source, week_records):
    source = fake_source(week_records)
    monkeypatch.setattr(routes, "get_reports_source", lambda: source)
    client = create_app(False).test_client()
    resp = client.get("/admin/pooled")
    assert resp.status_code == 200
    assert 'data-chart="pooledTree"' in resp.get_data(as_text=True)


def test_admin_pooled_shows_no_data_message_when_empty(monkeypatch, fake_source):
    monkeypatch.setattr(routes, "get_reports_source", lambda: fake_source([]))
    client = create_app(False).test_client()
    resp = client.get("/admin/pooled")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'data-chart="pooledTree"' not in body
    assert "No per-user files found" in body
