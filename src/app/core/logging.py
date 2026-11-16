import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    def __init__(self, environment: str) -> None:
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": self.environment,
        }
        for key in ("request_id", "method", "path", "status_code", "duration_ms", "error_type"):
            if key in record.__dict__:
                payload[key] = record.__dict__[key]
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: str, environment: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(environment))
    logger = logging.getLogger("app")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
