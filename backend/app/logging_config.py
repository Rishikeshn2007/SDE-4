import logging
import json
from datetime import datetime, timezone
from contextvars import ContextVar


request_id_context = ContextVar("request_id", default=None)
correlation_id_context = ContextVar("correlation_id", default=None)


class JSONFormatter(logging.Formatter):

    def format(self, record):

        log_data = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": request_id_context.get(),
            "correlation_id": correlation_id_context.get(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(
                record.exc_info
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