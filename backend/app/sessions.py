from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel


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


class CreateSessionRequest(BaseModel):
    mode: str = "mock"


class UpdateSessionStateRequest(BaseModel):
    state: SessionState


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

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def update_state(
        self, session_id: str, new_state: SessionState
    ) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)

            if session is None:
                return None

            updated_session = session.model_copy(
                update={
                    "state": new_state,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

            self._sessions[session_id] = updated_session
            return updated_session