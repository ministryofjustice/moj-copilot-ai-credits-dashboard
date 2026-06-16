from flask import Flask

from app.main.middleware.error_handler import (
    client_error,
    page_not_found,
    server_forbidden,
    unknown_server_error,
)


def configure_error_handlers(app: Flask) -> None:
    app.register_error_handler(400, client_error)
    app.register_error_handler(403, server_forbidden)
    app.register_error_handler(404, page_not_found)
    app.register_error_handler(500, unknown_server_error)
