from pytest import approx

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


def _rec(day, user, credits):
    return {"day": day, "user": user, "credits": credits, "usd": credits / 100.0,
            "per_model": {"gpt": credits}}


def test_resolve_seats_defaults_and_validates():
    assert ac.resolve_seats("10") == 10
    assert ac.resolve_seats(None) == 405
    assert ac.resolve_seats("abc") == 405
    assert ac.resolve_seats("-5") == 405
    assert ac.resolve_seats("0") == 405
