import unittest
from flask import session

from app.app import create_app


class MainRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(False)
        self.app.config["SECRET_KEY"] = "test_flask"
        self.client = self.app.test_client()

    def test_index(self):
        @self.app.before_request
        def inject_mock_session():
            session["user"] = {
                "userinfo": {
                    "nickname": "test_user"
                }
            }

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
