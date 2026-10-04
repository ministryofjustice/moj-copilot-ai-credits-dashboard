"""Signing in and the admin check, with Auth0 switched on.

The rest of the suite runs with AUTH_DISABLED=true, so these are the only
tests that reach the real access checks. Auth0 itself is never called: the
service methods that would talk to it are replaced per test.
"""

from time import time

import pytest
from flask import session

from app.app import create_app
from app.main.config.app_config import app_config
from app.main.routes import ai_credits as routes
from app.main.routes import auth as auth_routes

# The claim requires_admin reads outside development.
_ROLE_CLAIM = ("https://check-my-copilot-ai-credits-usage.service.justice.gov.uk"
               "/org_role")


def _signed_in(nickname="alice", role=None, expires_in=3600):
    """What the Auth0 callback leaves in session["user"]."""
    userinfo = {"nickname": nickname}
    if role is not None:
        userinfo[_ROLE_CLAIM] = role
    return {"userinfo": userinfo, "expires_at": time() + expires_in}


def _client(monkeypatch, source, user=None):
    """A test client with login switched on, signed in as `user` if given."""
    monkeypatch.setattr(app_config, "auth_disabled", False)
    monkeypatch.setattr(app_config.flask, "app_env", "production")
    monkeypatch.setattr(routes, "get_reports_source", lambda: source)
    app = create_app(False)
    app.config["SECRET_KEY"] = "test_flask"
    if user is not None:
        @app.before_request
        def inject_session():  # pylint: disable=unused-variable
            session["user"] = user
    return app.test_client()


# ----------------------------------------------------------------- signing in
def test_a_visitor_without_a_session_is_sent_to_login(monkeypatch, fake_source):
    resp = _client(monkeypatch, fake_source([])).get("/admin/daily")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/auth/login"


def test_an_expired_session_is_sent_to_login(monkeypatch, fake_source):
    client = _client(monkeypatch, fake_source([]),
                     _signed_in(role="admin", expires_in=-60))
    resp = client.get("/admin/daily")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/auth/login"


def test_login_hands_auth0_an_https_callback(monkeypatch, fake_source):
    seen = []

    def fake_login(redirect_uri):
        seen.append(redirect_uri)
        return "redirected to Auth0"

    monkeypatch.setattr(auth_routes.auth0_service, "login", fake_login)
    _client(monkeypatch, fake_source([])).get("/auth/login")
    assert seen == ["https://localhost/auth/callback"]


def test_callback_returns_to_the_page_that_needed_login(monkeypatch,
                                                         fake_source):
    monkeypatch.setattr(auth_routes.auth0_service, "get_access_token",
                        lambda: _signed_in(role="admin"))
    client = _client(monkeypatch, fake_source([]))
    client.get("/admin/monthly?month=2026-06")
    resp = client.get("/auth/callback")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/admin/monthly?month=2026-06"
    assert client.get("/admin/monthly?month=2026-06").status_code == 200


def test_callback_with_no_saved_page_goes_to_my_usage(monkeypatch,
                                                       fake_source):
    monkeypatch.setattr(auth_routes.auth0_service, "get_access_token",
                        _signed_in)
    resp = _client(monkeypatch, fake_source([])).get("/auth/callback")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


@pytest.mark.xfail(strict=True, reason="logout builds its return URL from "
                   "'main.index', an endpoint that does not exist")
def test_logout_sends_the_user_to_auth0_to_finish(monkeypatch, fake_source):
    client = _client(monkeypatch, fake_source([]), _signed_in())
    resp = client.get("/auth/logout")
    assert resp.status_code == 302
    assert "/v2/logout?" in resp.headers["Location"]


# ------------------------------------------------------------------- my usage
def test_a_signed_in_user_sees_only_their_own_usage(monkeypatch, fake_source,
                                                    make_record):
    """With login on, ?user= is ignored: nobody can open someone else's page."""
    source = fake_source([make_record("2026-06-01", "alice", 10.0),
                          make_record("2026-06-01", "zz-someone-else", 20.0)])
    client = _client(monkeypatch, source, _signed_in("alice"))
    body = client.get("/?user=zz-someone-else").get_data(as_text=True)
    assert "GitHub username: <strong>alice</strong>" in body
    assert "zz-someone-else" not in body


# ---------------------------------------------------------------- admin pages
def test_an_admin_can_open_admin_pages(monkeypatch, fake_source):
    client = _client(monkeypatch, fake_source([]), _signed_in(role="admin"))
    resp = client.get("/admin/daily")
    assert resp.status_code == 200
    assert "No data found" in resp.get_data(as_text=True)


def test_every_admin_page_refuses_a_non_admin(monkeypatch, fake_source):
    client = _client(monkeypatch, fake_source([]), _signed_in(role="member"))
    paths = [rule.rule for rule in client.application.url_map.iter_rules()
             if rule.rule.startswith("/admin")]
    assert paths
    for path in paths:
        body = client.get(path).get_data(as_text=True)
        assert "Web server forbids you from accessing the page" in body, path


@pytest.mark.xfail(strict=True,
                   reason="requires_admin renders the 403 page with status 200")
def test_a_non_admin_gets_a_403_status(monkeypatch, fake_source):
    client = _client(monkeypatch, fake_source([]), _signed_in(role="member"))
    assert client.get("/admin/daily").status_code == 403
