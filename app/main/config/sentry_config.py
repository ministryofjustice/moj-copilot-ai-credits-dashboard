import logging

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

logger = logging.getLogger(__name__)


def configure_sentry(dsn_key: str, environment: str) -> None:
    if not dsn_key:
        logger.warning("Missing Sentry DSN Key")

    if not environment:
        logger.warning("Missing Sentry Environment")

    if dsn_key and environment:
        logger.info(f"Configuring Sentry for environment [ {environment} ]")
        sentry_sdk.init(
            dsn=dsn_key,
            environment=environment,
            integrations=[FlaskIntegration()],
            enable_tracing=True,
            traces_sample_rate=0.1,
        )
        logger.info("Sentry configured successfully")
    else:
        logger.warning(
            "Sentry not configured due to either missing DSN Key or Environment"
        )
