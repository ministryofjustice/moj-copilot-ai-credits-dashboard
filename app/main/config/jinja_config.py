from flask import Flask
from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader


def configure_jinja(app: Flask) -> None:
    app.jinja_loader = ChoiceLoader(
        [
            PackageLoader("app"),
            PrefixLoader(
                {"govuk_frontend_jinja": PackageLoader("govuk_frontend_jinja")}
            ),
        ]
    )
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True
