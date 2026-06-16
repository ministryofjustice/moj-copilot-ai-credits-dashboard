import unittest

from app.app import create_app


class MainRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(is_rate_limit_enabled=False)
        self.app.config["SECRET_KEY"] = "test"
        self.client = self.app.test_client()

    def test_index(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.status_code, "/")


if __name__ == "__main__":
    unittest.main()
