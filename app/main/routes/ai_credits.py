"""AI-credits dashboard routes.

Three pages, all state carried in the URL query string (the Flask-idiomatic
replacement for Streamlit's reactive widgets):

    /              My usage   — ?user=<login>&plan=<plan>
    /admin         Org daily  — ?day=YYYY-MM-DD
    /admin/weekly  Org weekly — ?plan=<plan>&week=YYYY-Www
    /admin/pooled  Org pooled — ?period=weekly|monthly&key=<key>&plan=<plan>&seats=<n>

The data backend is resolved per request via `get_reports_source()` (local files
today, S3/DB later) so these handlers never touch storage directly.
"""

from flask import Blueprint, render_template, request, session

from app.main.services import ai_credits as ac
from app.main.services.reports_source import get_reports_source
from app.main.middleware.auth import requires_auth, requires_admin
from app.main.config.app_config import app_config


ai_credits = Blueprint("ai_credits", __name__)


@ai_credits.route("/")
@requires_auth
def my_usage():
    source = get_reports_source()

    if app_config.auth_disabled:
        # No Auth0 session locally — take ?user= or stand in a random example user
        # (one of the top spenders, picked at runtime) so the page shows real data.
        username = request.args.get("user") or ac.example_login(source)
        role = request.args.get("role") or "admin"
    else:
        username = session["user"].get("userinfo", {}).get("nickname", "")
        role = session["user"].get("userinfo", {}).get("https://moj-copilot-ai-credits-dashboard-dev.cloud-platform.service.justice.gov.uk/org_role", "")

    print(f"Username: {username}")

    view = ac.user_view(
        source,
        username,
        role,
        request.args.get("plan"),
        request.args.get("month"),
    )

    return render_template("pages/my_usage.html", v=view)


@ai_credits.route("/admin")
@requires_auth
@requires_admin
def admin_daily():
    view = ac.daily_view(get_reports_source(), request.args.get("day"))
    return render_template("pages/admin_daily.html", v=view)


@ai_credits.route("/admin/weekly")
@requires_auth
@requires_admin
def admin_weekly():
    view = ac.weekly_view(
        get_reports_source(), request.args.get("plan"), request.args.get("week")
    )
    return render_template("pages/admin_weekly.html", v=view)


@ai_credits.route("/admin/pooled")
@requires_auth
@requires_admin
def admin_pooled():
    view = ac.pooled_view(
        get_reports_source(),
        request.args.get("period"),
        request.args.get("key"),
        request.args.get("plan"),
        request.args.get("seats"),
    )
    return render_template("pages/admin_pooled.html", v=view)
