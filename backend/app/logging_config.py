import logging
import json
import re

from datetime import datetime, timezone
from contextvars import ContextVar


request_id_context = ContextVar("request_id", default=None)
correlation_id_context = ContextVar("correlation_id", default=None)


SENSITIVE_PATTERNS = [
    re.compile(
        r'("?(?:X-Local-Auth|authorization|access_token|'
        r'password|api_key)"?\s*[:=]\s*)'
        r'("[^"]*"|[^,\s}]+)',
        re.IGNORECASE,
    ),
]


def redact_sensitive_data(message):
    for pattern in SENSITIVE_PATTERNS:
        message = pattern.sub(r'\1"[REDACTED]"', message)

    return message


class JSONFormatter(logging.Formatter):

    def format(self, record):

        log_data = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": redact_sensitive_data(
                record.getMessage()
            ),
            "logger": record.name,
            "request_id": request_id_context.get(),
            "correlation_id": correlation_id_context.get(),
        }

        if record.exc_info:
            log_data["exception"] = redact_sensitive_data(
                self.formatException(record.exc_info)
            )

        return json.dumps(log_data)


def setup_logging():

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    logger.handlers.clear()
    logger.addHandler(handler)


setup_logging()