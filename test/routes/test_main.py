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

    def _inject(self, nickname):
        @self.app.before_request
        def inject_mock_session():  # pylint: disable=unused-variable
            session["user"] = {"userinfo": {"nickname": nickname}}

    def test_index_unknown_user_renders(self):
        # AUTH_DISABLED is on in tests, so the username comes from ?user=.
        self._inject("ignored")
        response = self.client.get("/?user=definitely_not_a_real_login")
        self.assertEqual(response.status_code, 200)

    def test_index_found_user_renders_hero_cards(self):
        self._inject("ignored")
        rows = [{"day": "2026-06-22", "user_login": "alice", "credits": 120.0},
                {"day": "2026-06-23", "user_login": "alice", "credits": 30.0}]
        routes.get_reports_source = lambda: _FakeSource(rows)
        try:
            response = self.client.get("/?user=alice")
        finally:
            # restore the real factory for other tests
            from app.main.services.reports_source import get_reports_source
            routes.get_reports_source = get_reports_source
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Your usage so far", body)
        self.assertIn("This week (WTD)", body)


if __name__ == "__main__":
    unittest.main()
