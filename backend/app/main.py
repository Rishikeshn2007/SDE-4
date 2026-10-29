from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import ErrorEnvelope
from app.middleware import RequestCorrelationMiddleware
from app.sessions import (
    CreateSessionRequest,
    SessionRepository,
    SessionState,
    UpdateSessionStateRequest,
)

app = FastAPI(
    title="SDE-4 Voicebot Backend",
    description="Backend API with mock session management",
    version="1.0.0",
)

app.add_middleware(RequestCorrelationMiddleware)

repository = SessionRepository()


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


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    return make_error_response(
        request,
        422,
        "VALIDATION_ERROR",
        "The request contains invalid data.",
        details={"error_count": len(exc.errors())},
    )


@app.get("/")
async def root():
    return {
        "name": "SDE-4 Voicebot Backend",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/ready")
async def readiness():
    return {"status": "ready"}


@app.post("/sessions", status_code=201)
async def create_session(payload: CreateSessionRequest):
    if payload.mode != "mock":
        raise HTTPException(
            status_code=400,
            detail="Only mock mode is supported",
        )

    session = repository.create()
    return session.model_dump(mode="json")


@app.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    session = repository.get(session_id)

    if session is None:
        return make_error_response(
            request,
            404,
            "SESSION_NOT_FOUND",
            "The requested session was not found.",
        )

    return session.model_dump(mode="json")


@app.patch("/sessions/{session_id}/state")
async def update_session_state(
    session_id: str,
    payload: UpdateSessionStateRequest,
    request: Request,
):
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

    return session.model_dump(mode="json")