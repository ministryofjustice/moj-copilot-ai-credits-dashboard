import app.main.services.ai_credits as ac


class _FakeSource:
    def __init__(self, records):
        self._records = records

    def weekly_records(self):
        return self._records

    def daily_docs(self):
        return {}

    def per_user_docs(self, day):
        return {}


def test_user_view_includes_calendar_for_found_user():
    recs = [{"day": "2026-06-16", "user": "alice", "credits": 5.0,
             "usd": 0.05, "per_model": {"gpt": 5.0}}]
    v = ac.user_view(_FakeSource(recs), "alice", "$70 / month", None)
    assert v["found"] is True
    assert "calendar" in v
    assert len(v["calendar"]["weeks"]) == ac.HEATMAP_WEEKS
