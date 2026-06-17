from flask import Flask

from app.main.routes.ai_credits import ai_credits
from app.main.routes.robots import robot_route


def configure_routes(app: Flask) -> None:
    app.register_blueprint(ai_credits)
    app.register_blueprint(robot_route)
