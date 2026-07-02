import os
from types import SimpleNamespace


def __get_env_var(name: str) -> str | None:
    return os.getenv(name)


def __get_bool_env_var(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


app_config = SimpleNamespace(
    flask=SimpleNamespace(
        app_secret_key=__get_env_var("APP_SECRET_KEY"),
        app_env=__get_env_var("APP_ENV")
    ),
    # Local-dev escape hatch: when truthy, `requires_auth` is a no-op so the app
    # can run without a reachable Auth0 tenant. Never enable in deployed envs.
    auth_disabled=__get_bool_env_var("AUTH_DISABLED"),
    logging_level=__get_env_var("LOGGING_LEVEL"),
    sentry=SimpleNamespace(
        dsn_key=__get_env_var("SENTRY_DSN_KEY"), environment=__get_env_var("SENTRY_ENV")
    ),
    auth0=SimpleNamespace(
        domain=__get_env_var("AUTH0_DOMAIN"),
        client_id=__get_env_var("AUTH0_CLIENT_ID"),
        client_secret=__get_env_var("AUTH0_CLIENT_SECRET"),
    ),
)
