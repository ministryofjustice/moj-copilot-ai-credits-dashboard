"""Error pages must not leak internals (OWASP A05, CWE-209).

Exception text can carry filesystem paths, table names or Athena/SQL error
detail. Users get a generic message; the diagnostic detail goes to the logs,
where operators can still reach it.
"""

import logging

from app.app import create_app
from app.main.middleware.error_handler import client_error, unknown_server_error

SECRET_DETAIL = "s3://prod-bucket/reports table copilot_usage row 42"


class _WrappedError(Exception):
    """Stand-in for Flask's InternalServerError, which carries the real
    exception on `original_exception`."""

    def __init__(self, original):
        super().__init__("500 Internal Server Error")
        self.original_exception = original


def test_500_page_does_not_leak_exception_type_or_message():
    app = create_app(False)
    with app.test_request_context("/"):
        err = _WrappedError(RuntimeError(SECRET_DETAIL))
        body, status = unknown_server_error(err)
    assert status == 500
    assert SECRET_DETAIL not in body
    assert "RuntimeError" not in body


def test_500_page_shows_a_generic_message():
    app = create_app(False)
    with app.test_request_context("/"):
        body, _ = unknown_server_error(_WrappedError(RuntimeError(SECRET_DETAIL)))
    assert "Try again later" in body


def test_500_detail_still_reaches_the_logs(caplog):
    app = create_app(False)
    with app.test_request_context("/"), caplog.at_level(logging.INFO):
        unknown_server_error(_WrappedError(RuntimeError(SECRET_DETAIL)))
    assert SECRET_DETAIL in caplog.text


def test_400_page_does_not_leak_exception_message():
    app = create_app(False)
    with app.test_request_context("/"):
        body, status = client_error(ValueError(SECRET_DETAIL))
    assert status == 400
    assert SECRET_DETAIL not in body


def test_400_detail_still_reaches_the_logs(caplog):
    app = create_app(False)
    with app.test_request_context("/"), caplog.at_level(logging.INFO):
        client_error(ValueError(SECRET_DETAIL))
    assert SECRET_DETAIL in caplog.text
