from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def configure_limiter(app: Flask, is_rate_limit_enabled: bool = True) -> None:
    Limiter(
        get_remote_address,
        app=app,
        default_limits=["10 per minute", "2 per second"],
        storage_uri="memory://",
        strategy="moving-window",
        enabled=is_rate_limit_enabled,
    )
