
import logging

logger = logging.getLogger("siwi")


def log_info(message, app="general", **extra):
    extra["app"] = app
    logger.info(message, extra=extra)


def log_warning(message, app="general", **extra):
    extra["app"] = app
    logger.warning(message, extra=extra)


def log_error(message, app="general", **extra):
    extra["app"] = app
    logger.error(message, exc_info=True, extra=extra)