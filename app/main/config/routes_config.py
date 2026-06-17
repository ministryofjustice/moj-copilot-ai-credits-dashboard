from app.main.routes.ai_credits import ai_credits
from app.main.routes.robots import robot_route
from app.main.routes.auth import auth_route
from flask import Flask


def configure_routes(app: Flask) -> None:
    app.register_blueprint(auth_route, url_prefix="/auth")
    app.register_blueprint(ai_credits)
    app.register_blueprint(robot_route)
