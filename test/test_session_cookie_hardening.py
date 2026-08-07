"""Session cookie hardening (OWASP A05/A07).

The session cookie must never travel over plain HTTP (Secure), must be
invisible to page scripts (HttpOnly), and must be withheld from cross-site
subrequests while still accompanying top-level navigations (SameSite=Lax —
Strict would break the Auth0 callback, which reads the OAuth state from the
session on a cross-site redirect).
"""

import pytest

from app.app import create_app


@pytest.fixture()
def app():
    return create_app(False)


def test_session_cookie_is_secure(app):  # pylint: disable=redefined-outer-name
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_session_cookie_is_httponly(app):  # pylint: disable=redefined-outer-name
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True


def test_session_cookie_samesite_is_lax(app):  # pylint: disable=redefined-outer-name
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
