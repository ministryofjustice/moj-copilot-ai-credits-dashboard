from flask import (
    Blueprint,
    send_from_directory
)

robot_route = Blueprint("robot_route", __name__)


@robot_route.route("/robots.txt")
def send_robots_txt():
    return send_from_directory("static", "robots.txt")