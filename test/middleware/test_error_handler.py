from app.app import create_app
from app.main.middleware.error_handler import unknown_server_error


class _WrappedError(Exception):
    """Stand-in for Flask's InternalServerError, which carries the real
    exception on `original_exception`."""

    def __init__(self, original):
        super().__init__("500 Internal Server Error")
        self.original_exception = original


def test_500_handler_includes_exception_type_and_message():
    app = create_app(False)
    with app.test_request_context("/"):
        err = _WrappedError(RuntimeError("kaboom detail"))
        body, status = unknown_server_error(err)
    assert status == 500
    assert "RuntimeError" in body
    assert "kaboom detail" in body
