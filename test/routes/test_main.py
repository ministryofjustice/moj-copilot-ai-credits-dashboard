import unittest

from flask import session

from app.app import create_app
from app.main.routes import ai_credits as routes


class _FakeSource:
    def __init__(self, user_rows):
        self._user_rows = user_rows

    def user_rows(self):
        return self._user_rows

    def model_rows(self):
        return []


class MainRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(False)
        self.app.config["SECRET_KEY"] = "test_flask"
        self.client = self.app.test_client()
        # Routes import get_reports_source by name; stub it per test and restore
        # afterwards so none of them touch the real on-disk reports/ tree.
        self._real_source = routes.get_reports_source

    def tearDown(self):
        routes.get_reports_source = self._real_source

    def _inject(self, nickname):
        @self.app.before_request
        def inject_mock_session():  # pylint: disable=unused-variable
            session["user"] = {"userinfo": {"nickname": nickname}}

    def _use_source(self, rows):
        routes.get_reports_source = lambda: _FakeSource(rows)

    def test_index_unknown_user_renders(self):
        # AUTH_DISABLED is on in tests, so the username comes from ?user=.
        self._inject("ignored")
        self._use_source([])
        response = self.client.get("/?user=definitely_not_a_real_login")
        self.assertEqual(response.status_code, 200)

    def test_index_found_user_renders_hero_cards(self):
        self._inject("ignored")
        rows = [{"day": "2026-06-22", "user_login": "alice", "credits": 120.0},
                {"day": "2026-06-23", "user_login": "alice", "credits": 30.0}]
        self._use_source(rows)
        response = self.client.get("/?user=alice")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Your usage so far", body)
        self.assertIn("This week (WTD)", body)

    def test_index_budget_dropdown_offers_200_and_39_only(self):
        """My Usage measures against $200/seat/month; $70 is admin-only."""
        self._inject("ignored")
        rows = [{"day": "2026-06-22", "user_login": "alice", "credits": 120.0}]
        self._use_source(rows)
        body = self.client.get("/?user=alice").get_data(as_text=True)
        self.assertIn("$200 / month", body)
        self.assertIn("$39 / month", body)
        self.assertNotIn("$70 / month", body)

    def test_index_ignores_an_admin_only_plan_in_the_query(self):
        """A bookmarked ?plan=$70 falls back to the $200 default."""
        self._inject("ignored")
        rows = [{"day": "2026-06-22", "user_login": "alice", "credits": 120.0}]
        self._use_source(rows)
        body = self.client.get(
            "/?user=alice&plan=%2470+%2F+month").get_data(as_text=True)
        self.assertIn('value="$200 / month" selected', body)

    def test_index_in_progress_month_renders_pace_panel(self):
        self._inject("ignored")
        rows = [{"day": "2026-06-22", "user_login": "alice", "credits": 120.0},
                {"day": "2026-06-23", "user_login": "alice", "credits": 30.0}]
        self._use_source(rows)
        body = self.client.get("/?user=alice").get_data(as_text=True)
        self.assertIn("Projected Jun 2026 usage", body)

    def test_index_completed_month_hides_pace_panel(self):
        self._inject("ignored")
        # A July record marks June as fully captured — no June projection.
        rows = [{"day": "2026-06-22", "user_login": "alice", "credits": 120.0},
                {"day": "2026-07-02", "user_login": "alice", "credits": 30.0}]
        self._use_source(rows)
        body = self.client.get("/?user=alice&month=2026-06").get_data(as_text=True)
        self.assertNotIn("Projected Jun 2026 usage", body)


if __name__ == "__main__":
    unittest.main()
