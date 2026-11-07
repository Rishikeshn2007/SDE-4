from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from threading import Lock
import logging

from app.errors import ErrorEnvelope
from app.middleware import RequestCorrelationMiddleware

from app.sessions import (
    CreateSessionRequest,
    SessionRepository,
    SessionState,
    UpdateSessionStateRequest,
)

from app.events import router as events_router
from app.events import add_event

from app.logging_config import setup_logging


# Configure logging
setup_logging()

logger = logging.getLogger(__name__)


# Create FastAPI application
app = FastAPI(
    title="SDE-4 Voicebot Backend",
    description="Backend API with mock session management",
    version="1.0.0",
)

app.add_middleware(RequestCorrelationMiddleware)

app.include_router(events_router)


# Repository and idempotency storage
repository = SessionRepository()

idempotency_store = {}
idempotency_lock = Lock()


# Standard error response
def make_error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict | None = None,
):

    error = ErrorEnvelope(
        code=code,
        message_safe_for_user=message,
        retryable=retryable,
        correlation_id=getattr(
            request.state, "correlation_id", "unknown"
        ),
        details_redacted=details or {},
    )

    return JSONResponse(
        status_code=status_code,
        content={"error": error.model_dump()},
    )


# HTTP exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
):

    if exc.status_code == 404:
        code = "NOT_FOUND"
        message = "The requested resource was not found."
    else:
        code = "HTTP_ERROR"
        message = "The request could not be completed."

    return make_error_response(
        request,
        exc.status_code,
        code,
        message,
    )


# Validation exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):

    return make_error_response(
        request,
        422,
        "VALIDATION_ERROR",
        "The request contains invalid data.",
        details={"error_count": len(exc.errors())},
    )


# Root endpoint
@app.get("/")
async def root():

    return {
        "name": "SDE-4 Voicebot Backend",
        "status": "running",
    }


# Health endpoint
@app.get("/health")
async def health():

    return {"status": "healthy"}


# Readiness endpoint
@app.get("/ready")
async def readiness():

    return {"status": "ready"}


# Create session with idempotency
@app.post("/sessions", status_code=201)
async def create_session(
    payload: CreateSessionRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
):

    if payload.mode != "mock":
        raise HTTPException(
            status_code=400,
            detail="Only mock mode is supported",
        )

    if idempotency_key:

        if len(idempotency_key) > 128:
            raise HTTPException(
                status_code=400,
                detail="Idempotency key is too long",
            )

        with idempotency_lock:

            if idempotency_key in idempotency_store:
                logger.info("Duplicate idempotent request received")
                return idempotency_store[idempotency_key]

            session = repository.create()

            result = session.model_dump(mode="json")

            add_event(
                session.session_id,
                "session_created",
                {"state": "created"},
            )

            idempotency_store[idempotency_key] = result

            logger.info(
                "Session created: %s",
                session.session_id,
            )

            return result

    session = repository.create()

    add_event(
        session.session_id,
        "session_created",
        {"state": "created"},
    )

    logger.info(
        "Session created: %s",
        session.session_id,
    )

    return session.model_dump(mode="json")


# Get session
@app.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
):

    session = repository.get(session_id)

    if session is None:
        return make_error_response(
            request,
            404,
            "SESSION_NOT_FOUND",
            "The requested session was not found.",
        )

    return session.model_dump(mode="json")


# Update session state
@app.patch("/sessions/{session_id}/state")
async def update_session_state(
    session_id: str,
    payload: UpdateSessionStateRequest,
    request: Request,
):

    try:

        session = repository.update_state(
            session_id,
            payload.state,
        )

        if session is None:
            return make_error_response(
                request,
                404,
                "SESSION_NOT_FOUND",
                "The requested session was not found.",
            )

        add_event(
            session_id,
            "session_state_changed",
            {"state": session.state.value},
        )

        logger.info(
            "Session state updated: %s",
            session.state.value,
        )

        return session.model_dump(mode="json")

    except ValueError as exc:

        return make_error_response(
            request,
            409,
            "INVALID_SESSION_TRANSITION",
            str(exc),
        )


# Stop session
@app.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    request: Request,
):

    try:

        session = repository.update_state(
            session_id,
            SessionState.STOPPING,
        )

        if session is None:
            return make_error_response(
                request,
                404,
                "SESSION_NOT_FOUND",
                "The requested session was not found.",
            )

        session = repository.update_state(
            session_id,
            SessionState.COMPLETED,
        )

        add_event(
            session_id,
            "session_completed",
            {"state": "completed"},
        )

        logger.info(
            "Session completed: %s",
            session_id,
        )

        return session.model_dump(mode="json")

    except ValueError as exc:

        return make_error_response(
            request,
            409,
            "INVALID_SESSION_TRANSITION",
            str(exc),
        )