
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.logging_config import (
    request_id_context,
    correlation_id_context,
)


class RequestCorrelationMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        request_id = request.headers.get("X-Request-ID")

        if not request_id or len(request_id) > 128:
            request_id = str(uuid.uuid4())

        correlation_id = request.headers.get("X-Correlation-ID")

        if not correlation_id or len(correlation_id) > 128:
            correlation_id = request_id

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        request_token = request_id_context.set(request_id)
        correlation_token = correlation_id_context.set(
            correlation_id
        )

        try:
            response = await call_next(request)

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id

            return response

        finally:
            request_id_context.reset(request_token)
            correlation_id_context.reset(correlation_token)