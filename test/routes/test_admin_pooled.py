from app.app import create_app
from app.main.routes import ai_credits as routes
from app.main.services.reports_source import ReportsSource


class FakeSource(ReportsSource):
    def __init__(self, records):
        self._records = records

    def daily_docs(self):
        return {}

    def per_user_docs(self, day):
        return {}

    def weekly_records(self):
        return self._records


def _rec(day, user, credits):
    return {"day": day, "user": user, "credits": credits, "usd": credits / 100.0,
            "per_model": {"gpt": credits}}


def _records():
    return [
        _rec("2026-06-01", "a", 2000.0),
        _rec("2026-06-02", "b", 50.0),
        _rec("2026-06-03", "c", 30.0),
        _rec("2026-06-04", "d", 20.0),
    ]


def test_admin_pooled_renders_chart_when_data_present(monkeypatch):
    monkeypatch.setattr(routes, "get_reports_source", lambda: FakeSource(_records()))
    client = create_app(False).test_client()
    resp = client.get("/admin/pooled")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'data-chart="pooledTree"' in body


def test_admin_pooled_shows_no_data_message_when_empty(monkeypatch):
    monkeypatch.setattr(routes, "get_reports_source", lambda: FakeSource([]))
    client = create_app(False).test_client()
    resp = client.get("/admin/pooled")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'data-chart="pooledTree"' not in body
    assert "No per-user files found" in body
