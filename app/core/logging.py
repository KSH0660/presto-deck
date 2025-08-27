# app/core/logging.py

import logging
import sys


def configure_logging():
    """
    Configures the logging system for the application.
    """
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Default level

    # Create a console handler with a formatter
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)

    # Add the handler to the logger if not already added
    if not any(
        isinstance(handler, logging.StreamHandler) for handler in logger.handlers
    ):
        logger.addHandler(console_handler)

    # Set specific log levels for third-party libraries if needed
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # Suppress verbose httpx logs
    logging.getLogger("httpcore").setLevel(
        logging.WARNING
    )  # Suppress verbose httpcore logs

    # Example of how to get a logger in other modules:
    # logger = logging.getLogger(__name__)
    # logger.info("This is an info message from a module.")
