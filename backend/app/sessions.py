from app.config import settings
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel


# Sessions expire after 30 minutes without activity.
SESSION_TTL = timedelta(minutes=settings.session_ttl_minutes)


class SessionState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class Session(BaseModel):
    session_id: str
    state: SessionState
    created_at: datetime
    updated_at: datetime

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "123e4567-e89b-12d3-a456-426614174000",
                    "state": "created",
                    "created_at": "2026-11-28T10:00:00+00:00",
                    "updated_at": "2026-11-28T10:00:00+00:00",
                }
            ]
        }
    }


class CreateSessionRequest(BaseModel):
    mode: str = "mock"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"mode": "mock"}
            ]
        }
    }


class UpdateSessionStateRequest(BaseModel):
    state: SessionState

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"state": "active"},
                {"state": "paused"},
            ]
        }
    }


# Define permitted transitions from each state.
ALLOWED_TRANSITIONS = {
    SessionState.CREATED: {
        SessionState.ACTIVE,
        SessionState.STOPPING,
        SessionState.FAILED,
    },
    SessionState.ACTIVE: {
        SessionState.PAUSED,
        SessionState.STOPPING,
        SessionState.FAILED,
    },
    SessionState.PAUSED: {
        SessionState.ACTIVE,
        SessionState.STOPPING,
        SessionState.FAILED,
    },
    SessionState.STOPPING: {
        SessionState.COMPLETED,
        SessionState.FAILED,
    },
    SessionState.COMPLETED: set(),
    SessionState.FAILED: set(),
    SessionState.EXPIRED: set(),
}


class InvalidSessionTransition(ValueError):
    """Raised when a session state transition is not permitted."""


class SessionRepository:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()

    def create(self) -> Session:
        now = datetime.now(timezone.utc)

        session = Session(
            session_id=str(uuid4()),
            state=SessionState.CREATED,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._sessions[session.session_id] = session

        return session

    def _expire_if_needed(self, session: Session) -> Session:
        now = datetime.now(timezone.utc)

        if (
            session.state
            not in {
                SessionState.COMPLETED,
                SessionState.FAILED,
                SessionState.EXPIRED,
            }
            and now - session.updated_at >= SESSION_TTL
        ):
            session = session.model_copy(
                update={
                    "state": SessionState.EXPIRED,
                    "updated_at": now,
                }
            )
            self._sessions[session.session_id] = session

        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)

            if session is None:
                return None

            return self._expire_if_needed(session)

    def update_state(
        self, session_id: str, new_state: SessionState
    ) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)

            if session is None:
                return None

            session = self._expire_if_needed(session)

            if session.state == new_state:
                return session

            if new_state not in ALLOWED_TRANSITIONS[session.state]:
                raise InvalidSessionTransition(
                    f"Cannot transition session from "
                    f"'{session.state.value}' to '{new_state.value}'."
                )

            updated_session = session.model_copy(
                update={
                    "state": new_state,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

            self._sessions[session_id] = updated_session
            return updated_session