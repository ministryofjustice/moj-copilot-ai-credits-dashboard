import logging
from functools import wraps
from time import time

from flask import (
    redirect,
    session,
    request,
    render_template
)

from app.main.config.app_config import app_config

logger = logging.getLogger(__name__)


def requires_auth(function_f):
    @wraps(function_f)
    def decorated(*args, **kwargs):
        if app_config.auth_disabled:
            return function_f(*args, **kwargs)
        if "user" not in session or session["user"].get("expires_at", 0) < time():
            session.pop("user", None)
            session["post_auth_redirect_path"] = request.full_path
            return redirect("/auth/login")
        return function_f(*args, **kwargs)

    return decorated


def requires_admin(function_f):
    @wraps(function_f)
    def decorated(*args, **kwargs):
        if app_config.auth_disabled:
            return function_f(*args, **kwargs)

        if app_config.flask.app_env == "development":
            role = "admin"
        else:
            role = session["user"].get("userinfo", {}).get(f"https://moj-copilot-ai-credits-dashboard-prod.cloud-platform.service.justice.gov.uk/org_role", "")

        print(f"APP_ENV: {app_config.flask.app_env}")
        print(f"User role: {role}")

        if role == "admin":
            return function_f(*args, **kwargs)

        return render_template("pages/errors/403.html")

    return decorated
