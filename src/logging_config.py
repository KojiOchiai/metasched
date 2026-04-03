import logging
import os
from datetime import datetime

from pythonjsonlogger import jsonlogger


def setup_logging(log_dir: str = "logs"):
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    root_logger.setLevel(logging.DEBUG)

    # File handler: JSON, all levels
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_handler = logging.FileHandler(
        os.path.join(log_dir, f"metasched_{timestamp}.log"),
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    formatter = jsonlogger.JsonFormatter(
        "{asctime}{levelname}{name}{message}",
        style="{",
        json_ensure_ascii=False,
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Suppress noisy library loggers
    logging.getLogger("websockets").setLevel(logging.INFO)
