import logging

from pythonjsonlogger import jsonlogger


def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not root_logger.handlers:  # stop adding multiple handlers
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            "{levelname}{name}", timestamp=True, style="{", json_ensure_ascii=False
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
