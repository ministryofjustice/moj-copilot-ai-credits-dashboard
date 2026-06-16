from app.main.routes.main import main
from app.main.routes.robots import robot_route
from flask import Flask


def configure_routes(app: Flask) -> None:
    app.register_blueprint(main)
    app.register_blueprint(robot_route)
