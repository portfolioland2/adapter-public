import logging
from datetime import datetime
from typing import Any

import structlog
from structlog import wrap_logger

from src.config import settings


LOG_PATH = "/var/log/" if settings.ENV != "local" else ""


def add_handlers(logger: Any) -> Any:
    log_formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    if settings.ENV == "prod":
        file_handler = logging.FileHandler(f"{LOG_PATH}{logger.name}.log")
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)


def get_logger(logger: str) -> Any:
    root_logger = add_handlers(logging.getLogger(logger))

    log = wrap_logger(
        root_logger,
        processors=[
            add_version,  # type: ignore
            add_timestamp,  # type: ignore
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
    )
    return log


def add_timestamp(_: Any, __: str, event_dict: dict) -> dict:
    event_dict["timestamp"] = datetime.utcnow().strftime("%Y.%m.%d %H:%M:%S")
    return event_dict


def add_version(_: Any, __: str, event_dict: dict) -> dict:
    event_dict["version"] = settings.VERSION
    return event_dict
