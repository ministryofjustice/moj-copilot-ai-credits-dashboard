import logging


def configure_logging(logging_level: str) -> None:
    logging.basicConfig(
        format="{asctime:s} | {levelname:>8s} | {filename:s}:{lineno:d} | {message:s}",
        datefmt="%Y-%m-%dT%H:%M:%S",
        style="{",
        level=logging_level.upper() if logging_level else "INFO",
    )
