from app.main.services import ai_credits as ac
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


def _records():
    return [
        {"day": "2026-06-01", "user": "alice", "credits": 10.0, "usd": 0.1,
         "per_model": {"gpt": 10.0}},
        {"day": "2026-06-08", "user": "alice", "credits": 5.0, "usd": 0.05,
         "per_model": {"gpt": 5.0}},
    ]


def test_weekly_view_exposes_week_ranges():
    view = ac.weekly_view(FakeSource(_records()), plan=None, week="2026-W23")
    assert view["week_ranges"]["2026-W23"] == "1–7 Jun"
    assert view["week_ranges"]["2026-W24"] == "8–14 Jun"


def test_user_view_exposes_week_ranges_and_chart_labels():
    view = ac.user_view(FakeSource(_records()), login="alice", plan=None)
    assert view["week_ranges"]["2026-W23"] == "1–7 Jun"
    assert view["weekly_chart"]["labels"] == [
        "2026-W23 (1–7 Jun)",
        "2026-W24 (8–14 Jun)",
    ]
