import ipaddress
import secrets
import time

from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.errors import ErrorEnvelope


class SecurityMiddleware(BaseHTTPMiddleware):

    def __init__(self, app):
        super().__init__(app)
        self.requests = {}
        self.lock = Lock()

    def is_local_request(self, request: Request):
        if request.client is None:
            return False

        host = request.client.host

        if host == "testclient":
            return True

        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def error_response(
        self,
        request,
        status_code,
        code,
        message,
    ):
        error = ErrorEnvelope(
            code=code,
            message_safe_for_user=message,
            retryable=False,
            correlation_id=getattr(
                request.state,
                "correlation_id",
                request.headers.get(
                    "X-Correlation-ID",
                    "unknown",
                ),
            ),
            details_redacted={},
        )

        return JSONResponse(
            status_code=status_code,
            content={"error": error.model_dump()},
        )

    async def dispatch(self, request: Request, call_next):

        if request.url.path.startswith("/sessions"):

            # Check local access
            if not self.is_local_request(request):
                return self.error_response(
                    request,
                    403,
                    "LOCAL_ACCESS_ONLY",
                    "This endpoint is available only locally.",
                )

            # Check authentication key
            provided_token = request.headers.get(
                "X-Local-Auth",
                "",
            )

            if not secrets.compare_digest(
                provided_token,
                settings.local_auth_token,
            ):
                return self.error_response(
                    request,
                    401,
                    "LOCAL_AUTH_REQUIRED",
                    "A valid local authentication key is required.",
                )

        # Rate limiting
        if (
            request.method == "POST"
            and request.url.path.endswith("/process")
        ):
            client_host = request.client.host

            now = time.monotonic()
            window = settings.rate_limit_window
            limit = settings.rate_limit_requests

            with self.lock:
                recent_requests = self.requests.get(
                    client_host,
                    [],
                )

                recent_requests = [
                    timestamp
                    for timestamp in recent_requests
                    if now - timestamp < window
                ]

                if len(recent_requests) >= limit:
                    self.requests[client_host] = recent_requests

                    return self.error_response(
                        request,
                        429,
                        "RATE_LIMIT_EXCEEDED",
                        "Too many requests. Please try again later.",
                    )

                recent_requests.append(now)
                self.requests[client_host] = recent_requests

        return await call_next(request)