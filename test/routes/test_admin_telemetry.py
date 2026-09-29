"""The org telemetry admin page, rendered through the Flask test client."""

import json

from routes.test_admin_views import _admin_client


def _charts(body):
    """The chart specifications the page embeds for charts.js."""
    marker = 'id="chart-data">'
    start = body.index(marker) + len(marker)
    return json.loads(body[start:body.index("</script>", start)])


def _rows():
    user_rows = [
        {"day": "2026-08-03", "user_login": "zz-secret-login",
         "suggested": 40, "interactions": 5, "used_chat": True},
        {"day": "2026-07-30", "user_login": "zz-other-login",
         "suggested": 10},
    ]
    activity_rows = [
        {"day": "2026-08-03", "user_login": "zz-secret-login",
         "language": "python", "mode": "Inline completion",
         "suggested": 40, "accepted": 16},
    ]
    return user_rows, activity_rows


def test_every_admin_page_links_to_the_telemetry_tab(monkeypatch, fake_source):
    client = _admin_client(monkeypatch, fake_source([]))
    body = client.get("/admin/monthly").get_data(as_text=True)
    assert 'href="/admin/telemetry"' in body


def test_page_says_when_telemetry_is_not_configured(monkeypatch, org_source):
    client = _admin_client(monkeypatch, org_source(available=False))
    resp = client.get("/admin/telemetry")
    assert resp.status_code == 200
    assert "Telemetry is not configured" in resp.get_data(as_text=True)


def test_page_says_when_there_is_no_telemetry(monkeypatch, org_source):
    client = _admin_client(monkeypatch, org_source())
    body = client.get("/admin/telemetry").get_data(as_text=True)
    assert "No telemetry has been recorded" in body


def test_page_shows_tiles_and_the_capability_chart(monkeypatch, org_source):
    client = _admin_client(monkeypatch, org_source(*_rows()))
    body = client.get("/admin/telemetry").get_data(as_text=True)
    assert 'aria-current="page" href="/admin/telemetry"' in body
    for label in ("Days covered", "People with any activity", "Suggestions",
                  "Inline completions accepted", "Lines of code applied",
                  "Inline completion lines kept",
                  "User-initiated interactions", "CLI and app requests",
                  "Languages seen"):
        assert label in body
    spec = _charts(body)["capability_share"]
    assert spec["type"] == "line"
    assert spec["suffix"] == "%"
    assert spec["datasets"][0]["label"] == "Chat"


def test_month_dropdown_selects_the_requested_month(monkeypatch, org_source):
    client = _admin_client(monkeypatch, org_source(*_rows()))
    body = client.get("/admin/telemetry?month=2026-07").get_data(as_text=True)
    assert "What the organisation did in Jul 2026" in body


def test_page_shows_no_login(monkeypatch, org_source):
    client = _admin_client(monkeypatch, org_source(*_rows()))
    body = client.get("/admin/telemetry").get_data(as_text=True)
    assert "zz-secret-login" not in body
    assert "zz-other-login" not in body


def test_page_draws_the_daily_charts(monkeypatch, org_source):
    client = _admin_client(monkeypatch, org_source(*_rows()))
    charts = _charts(client.get("/admin/telemetry").get_data(as_text=True))
    assert [d["label"] for d in charts["daily_activity"]["datasets"]] == [
        "Suggestions", "Acceptances", "User-initiated interactions"]
    assert "daily_inline_rate" not in charts
    people = charts["daily_people"]
    assert people["type"] == "bar"
    assert people["datasets"][0]["colors"] == ["#1d70b8"]  # 2026-08-03 is a Monday
    assert [d["label"] for d in charts["daily_lines"]["datasets"]] == [
        "Lines suggested", "Lines applied"]


def test_page_draws_the_language_charts(monkeypatch, org_source):
    client = _admin_client(monkeypatch, org_source(*_rows()))
    charts = _charts(client.get("/admin/telemetry").get_data(as_text=True))
    for name in ("language_volume", "language_inline_rate", "language_lines"):
        assert charts[name]["horizontal"] is True
        assert charts[name]["labels"] == ["Python"]
    assert charts["language_inline_rate"]["suffix"] == "%"


def test_page_draws_the_mode_charts(monkeypatch, org_source):
    client = _admin_client(monkeypatch, org_source(*_rows()))
    charts = _charts(client.get("/admin/telemetry").get_data(as_text=True))
    assert charts["mode_volume"]["horizontal"] is True
    assert charts["mode_volume"]["labels"] == ["Inline completion"]
    people = charts["mode_people"]["datasets"][0]
    assert people["data"] == [1]
    assert people["colors"] == ["#1d70b8"]
