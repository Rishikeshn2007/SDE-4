from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from threading import Lock
import logging

from app.errors import ErrorEnvelope
from app.config import settings
from app.middleware import RequestCorrelationMiddleware
from app.security import SecurityMiddleware

from app.sessions import (
    CreateSessionRequest,
    SessionRepository,
    SessionState,
    UpdateSessionStateRequest,
)

from app.events import router as events_router
from app.events import add_event

from app.logging_config import setup_logging
from app.gateways.audio import AudioGateway
from app.gateways.transcription import TranscriptionGateway
from app.gateways.reasoning import ReasoningGateway
from app.gateways.workflow import WorkflowGateway


# Configure logging
setup_logging()

logger = logging.getLogger(__name__)


# Create FastAPI application
app = FastAPI(
    title="SDE-4 Voicebot Backend",
    description="Backend API with mock session management",
    version="1.0.0",
)


class PayloadLimitRoute(APIRoute):
    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request):
            body = await request.body()

            if len(body) > settings.max_event_payload_size:
                error = ErrorEnvelope(
                    code="PAYLOAD_TOO_LARGE",
                    message_safe_for_user="Request payload is too large.",
                    retryable=False,
                    correlation_id=getattr(
                        request.state,
                        "correlation_id",
                        "unknown",
                    ),
                    details_redacted={
                        "max_size": settings.max_event_payload_size,
                        "actual_size": len(body),
                    },
                )

                return JSONResponse(
                    status_code=413,
                    content={"error": error.model_dump()},
                )

            return await original_handler(request)

        return custom_handler


app.router.route_class = PayloadLimitRoute

# Register middleware
app.add_middleware(SecurityMiddleware)
app.add_middleware(RequestCorrelationMiddleware)

app.include_router(events_router)


# Repository and idempotency storage
repository = SessionRepository()

audio_gateway = AudioGateway()
transcription_gateway = TranscriptionGateway()
reasoning_gateway = ReasoningGateway()
workflow_gateway = WorkflowGateway()

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
@app.get(
    "/",
    summary="Root",
    description="Check whether the backend application is running.",
    responses={
        200: {
            "description": "Backend is running.",
            "content": {
                "application/json": {
                    "example": {
                        "name": "SDE-4 Voicebot Backend",
                        "status": "running"
                    }
                }
            }
        }
    }
)
async def root():

    return {
        "name": "SDE-4 Voicebot Backend",
        "status": "running",
    }


# Health endpoint
@app.get(
    "/health",
    summary="Health",
    description="Check the health of all backend gateway modules.",
    responses={
        200: {
            "description": "Health status of all modules.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "modules": {
                            "audio": {
                                "module": "audio",
                                "status": "healthy",
                                "mode": "mock"
                            },
                            "transcription": {
                                "module": "transcription",
                                "status": "healthy",
                                "mode": "mock"
                            },
                            "reasoning": {
                                "module": "reasoning",
                                "status": "healthy",
                                "mode": "mock"
                            },
                            "workflow": {
                                "module": "workflow",
                                "status": "healthy",
                                "mode": "mock"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def health():
    modules = {
        "audio": audio_gateway.health(),
        "transcription": transcription_gateway.health(),
        "reasoning": reasoning_gateway.health(),
        "workflow": workflow_gateway.health(),
    }

    all_healthy = all(
        module["status"] == "healthy"
        for module in modules.values()
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "modules": modules,
    }

# Readiness endpoint
@app.get(
    "/ready",
    summary="Readiness",
    description="Check whether the backend is ready to accept requests.",
    responses={
        200: {
            "description": "Backend is ready.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ready"
                    }
                }
            }
        }
    }
)
async def readiness():

    return {"status": "ready"}


# Create session with idempotency
@app.post(
    "/sessions",
    status_code=201,
    summary="Create Session",
    description="Create a new mock voicebot session.",
    responses={
        201: {
            "description": "Session created successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "123e4567-e89b-12d3-a456-426614174000",
                        "state": "created",
                        "created_at": "2026-11-28T10:00:00+00:00",
                        "updated_at": "2026-11-28T10:00:00+00:00"
                    }
                }
            }
        }
    }
)
async def create_session(
    payload: CreateSessionRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
):
    if not settings.mock_mode:
        raise HTTPException(
            status_code=503,
            detail="Mock mode is disabled and live mode is not configured",
        )

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

            logger.info("Session created: %s", session.session_id)
            return result

    session = repository.create()

    add_event(
        session.session_id,
        "session_created",
        {"state": "created"},
    )

    logger.info("Session created: %s", session.session_id)

    return session.model_dump(mode="json")


# Get session
@app.get(
    "/sessions/{session_id}",
    summary="Get Session",
    description="Retrieve an existing session using its session ID.",
    responses={
        200: {
            "description": "Session retrieved successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "123e4567-e89b-12d3-a456-426614174000",
                        "state": "active",
                        "created_at": "2026-11-28T10:00:00+00:00",
                        "updated_at": "2026-11-28T10:05:00+00:00"
                    }
                }
            }
        }
    }
)
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
@app.patch(
    "/sessions/{session_id}/state",
    summary="Update Session State",
    description="Change the state of an existing session.",
    responses={
        200: {
            "description": "Session state updated successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "123e4567-e89b-12d3-a456-426614174000",
                        "state": "active",
                        "created_at": "2026-11-28T10:00:00+00:00",
                        "updated_at": "2026-11-28T10:05:00+00:00"
                    }
                }
            }
        }
    }
)
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
@app.post(
    "/sessions/{session_id}/stop",
    summary="Stop Session",
    description="Stop an existing session and mark it completed.",
    responses={
        200: {
            "description": "Session stopped successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "123e4567-e89b-12d3-a456-426614174000",
                        "state": "completed",
                        "created_at": "2026-11-28T10:00:00+00:00",
                        "updated_at": "2026-11-28T10:10:00+00:00"
                    }
                }
            }
        }
    }
)
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


# Process session through all module gateways
@app.post(
    "/sessions/{session_id}/process",
    summary="Process Session",
    description="Process a session through audio, transcription, reasoning and workflow gateways.",
    responses={
        200: {
            "description": "Mock pipeline completed successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "123e4567-e89b-12d3-a456-426614174000",
                        "correlation_id": "abc-123",
                        "status": "success",
                        "mode": "mock",
                        "modules": [
                            {
                                "module": "audio",
                                "status": "success",
                                "message": "Mock audio received"
                            },
                            {
                                "module": "transcription",
                                "status": "success",
                                "transcript": "Hello, this is a mock voice input."
                            },
                            {
                                "module": "reasoning",
                                "status": "success",
                                "intent": "general_query"
                            },
                            {
                                "module": "workflow",
                                "status": "success",
                                "result": "Mock workflow completed."
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def process_session(
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

    correlation_id = getattr(
        request.state,
        "correlation_id",
        "unknown",
    )

    # Step 1: Audio
    audio_result = audio_gateway.process(
        session_id,
        correlation_id,
    )

    # Step 2: Transcription
    transcription_result = transcription_gateway.process(
        session_id,
        correlation_id,
        audio_result,
    )

    # Step 3: Reasoning
    reasoning_result = reasoning_gateway.process(
        session_id,
        correlation_id,
        transcription_result,
    )

    # Step 4: Workflow
    workflow_result = workflow_gateway.process(
        session_id,
        correlation_id,
        reasoning_result,
    )

    results = [
        audio_result,
        transcription_result,
        reasoning_result,
        workflow_result,
    ]

    for result in results:
        add_event(
            session_id,
            "gateway_processed",
            result,
        )

    logger.info(
        "Complete mock pipeline processed session: %s",
        session_id,
    )

    return {
        "session_id": session_id,
        "correlation_id": correlation_id,
        "status": "success",
        "mode": "mock",
        "modules": results,
    }