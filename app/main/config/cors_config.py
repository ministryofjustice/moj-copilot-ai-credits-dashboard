from flask import Flask
from flask_cors import CORS


def configure_cors(app: Flask) -> None:
    CORS(app, resources={r"/*": {"origins": "*", "send_wildcard": "False"}})
