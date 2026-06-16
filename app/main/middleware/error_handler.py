import logging

from flask import render_template

logger = logging.getLogger(__name__)


def client_error(err: Exception):
    logger.info("There was an error with the client request %s", err)
    return render_template("pages/errors/400.html", error_message=str(err)), 400


def page_not_found(err: Exception):
    logger.info("A request was made to a page that doesn't exist %s", err)
    return render_template("pages/errors/404.html"), 404


def server_forbidden(err: Exception):
    logger.info("server_forbidden(): %s", err)
    return render_template("pages/errors/403.html"), 403


def unknown_server_error(err: Exception):
    logger.info("An unknown server error occurred: %s", err)
    return render_template("pages/errors/500.html"), 500


def gateway_timeout(err: Exception):
    logger.info("A gateway timeout error occurred: %s", err)
    return render_template("pages/errors/504.html"), 504
