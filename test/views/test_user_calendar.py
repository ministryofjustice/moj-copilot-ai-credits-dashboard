import app.main.services.ai_credits as ac


def test_user_view_includes_calendar_for_found_user(fake_source):
    rows = [{"day": "2026-06-16", "user_login": "alice", "credits": 5.0}]
    v = ac.user_view(fake_source(rows), "alice", "$200 / month", None)
    assert v["found"] is True
    assert "calendar" in v
    assert len(v["calendar"]["weeks"]) == ac.HEATMAP_WEEKS
