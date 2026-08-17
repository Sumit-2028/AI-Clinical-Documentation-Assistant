import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

from .config import settings


_UUID_PATH_RE = re.compile(
    r"(?i)(?<![0-9a-f])"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
    r"(?![0-9a-f])"
)


def redact_request_path(path: str) -> str:
    """Remove UUID resource identifiers before a request path is logged."""

    return _UUID_PATH_RE.sub("<id>", path)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key in (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "error_type",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        return json.dumps(payload, default=str)


def setup_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())
    # Third-party request/SQL loggers can include URLs, query strings, SQL,
    # or bound values. Keep them below INFO unless explicitly configured by a
    # deployment with an approved redaction policy.
    for logger_name in ("httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


__all__ = ["JsonFormatter", "redact_request_path", "setup_logging"]
