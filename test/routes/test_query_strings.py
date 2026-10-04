"""Every page takes its state from the query string, so every query value is
untrusted input. A hostile value must neither break a page nor be echoed back
unescaped."""

import pytest

from routes.test_admin_views import _admin_client

PROBE = "<script>alert(1)</script>"


@pytest.fixture(name="client")
def _client(monkeypatch, fake_source, week_records, mrows):
    return _admin_client(monkeypatch, fake_source(week_records, mrows))


@pytest.mark.parametrize("path, param", [
    ("/", "user"), ("/", "plan"), ("/", "month"),
    ("/admin/daily", "day"),
    ("/admin/weekly", "plan"), ("/admin/weekly", "week"),
    ("/admin/monthly", "plan"), ("/admin/monthly", "month"),
    ("/admin/pooled", "period"), ("/admin/pooled", "key"),
    ("/admin/pooled", "plan"), ("/admin/pooled", "seats"),
])
def test_credit_pages_survive_and_escape_a_hostile_value(client, path, param):
    resp = client.get(path, query_string={param: PROBE})
    assert resp.status_code == 200
    assert PROBE not in resp.get_data(as_text=True)


def test_telemetry_page_survives_and_escapes_a_hostile_month(monkeypatch,
                                                             org_source):
    rows = [{"day": "2026-08-03", "user_login": "a", "suggested": 1}]
    client = _admin_client(monkeypatch, org_source(rows))
    resp = client.get("/admin/telemetry", query_string={"month": PROBE})
    assert resp.status_code == 200
    assert PROBE not in resp.get_data(as_text=True)
