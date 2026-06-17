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

from flask import Blueprint, render_template, request

from app.main.services import ai_credits as ac
from app.main.services.reports_source import get_reports_source

ai_credits = Blueprint("ai_credits", __name__)


@ai_credits.route("/")
def my_usage():
    view = ac.user_view(
        get_reports_source(),
        request.args.get("user"),
        request.args.get("plan"),
        request.args.get("week"),
    )
    return render_template("pages/my_usage.html", v=view)


@ai_credits.route("/admin")
def admin_daily():
    view = ac.daily_view(get_reports_source(), request.args.get("day"))
    return render_template("pages/admin_daily.html", v=view)


@ai_credits.route("/admin/weekly")
def admin_weekly():
    view = ac.weekly_view(
        get_reports_source(), request.args.get("plan"), request.args.get("week")
    )
    return render_template("pages/admin_weekly.html", v=view)


@ai_credits.route("/admin/pooled")
def admin_pooled():
    view = ac.pooled_view(
        get_reports_source(),
        request.args.get("period"),
        request.args.get("key"),
        request.args.get("plan"),
        request.args.get("seats"),
    )
    return render_template("pages/admin_pooled.html", v=view)
