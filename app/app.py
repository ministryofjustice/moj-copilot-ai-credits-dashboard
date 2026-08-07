# pylint: disable=C0411
import logging

from flask import Flask

from app.main.config.app_config import app_config
from app.main.config.error_handlers_config import configure_error_handlers
from app.main.config.jinja_config import configure_jinja
from app.main.config.limiter_config import configure_limiter
from app.main.config.logging_config import configure_logging
from app.main.config.routes_config import configure_routes
from app.main.config.sentry_config import configure_sentry

logger = logging.getLogger(__name__)


def create_app(is_rate_limit_enabled=True) -> Flask:
    configure_logging(app_config.logging_level)

    logger.info("Starting app...")

    app = Flask(__name__, static_folder="static", static_url_path="/assets")

    app.secret_key = app_config.flask.app_secret_key
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        # Lax, not Strict: the Auth0 callback is a top-level cross-site
        # redirect and Authlib reads the OAuth state from the session there.
        SESSION_COOKIE_SAMESITE="Lax",
    )

    configure_routes(app)
    configure_error_handlers(app)
    configure_sentry(app_config.sentry.dsn_key, app_config.sentry.environment)
    configure_limiter(app, is_rate_limit_enabled)
    configure_jinja(app)

    logger.info("Running app...")

    return app
