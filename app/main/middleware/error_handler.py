import logging

from flask import render_template

logger = logging.getLogger(__name__)


def client_error(err: Exception):
    logger.info("There was an error with the client request %s", err)
    return render_template("pages/errors/400.html"), 400


def page_not_found(err: Exception):
    logger.info("A request was made to a page that doesn't exist %s", err)
    return render_template("pages/errors/404.html"), 404


def server_forbidden(err: Exception):
    logger.info("server_forbidden(): %s", err)
    return render_template("pages/errors/403.html"), 403


def unknown_server_error(err: Exception):
    # The detail stays server-side: the page must not carry paths, table names
    # or query text back to the user (CWE-209). Log the original exception
    # rather than the wrapper, whose message is only "500 Internal Server Error".
    original = getattr(err, "original_exception", None) or err
    logger.error(
        "An unknown server error occurred: %s: %s",
        type(original).__name__,
        original,
        exc_info=original,
    )
    return render_template("pages/errors/500.html"), 500


def gateway_timeout(err: Exception):
    logger.info("A gateway timeout error occurred: %s", err)
    return render_template("pages/errors/504.html"), 504
