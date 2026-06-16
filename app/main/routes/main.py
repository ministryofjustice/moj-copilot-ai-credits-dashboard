from flask import Blueprint, current_app, redirect, render_template, request

main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("pages/main.html")
