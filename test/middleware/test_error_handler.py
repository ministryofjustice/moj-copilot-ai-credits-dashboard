from werkzeug.exceptions import InternalServerError

from app.app import create_app
from app.main.middleware.error_handler import unknown_server_error


def test_500_handler_includes_exception_type_and_message():
    app = create_app(False)
    with app.test_request_context("/"):
        err = InternalServerError(original_exception=RuntimeError("kaboom detail"))
        body, status = unknown_server_error(err)
    assert status == 500
    assert "RuntimeError" in body
    assert "kaboom detail" in body
