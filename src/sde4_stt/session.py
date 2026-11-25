"""
Session Management for Speech-to-Text (Week 3, D15-16).

Provides session-aware context objects that hold per-session state including
cancellation tokens and configurable confidence thresholds.

Components:
    - CancellationToken: Thread-safe flag that signals cancellation of a session.
    - SessionContext: Per-session state container (session_id, threshold, cancel token).
    - SessionManager: Creates, retrieves, and cancels sessions by session_id.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional


class CancellationToken:
    """Thread-safe cancellation signal for a transcription session.

    Usage::

        token = CancellationToken()
        # In producer thread:
        token.cancel()
        # In consumer thread:
        if token.is_cancelled:
            break
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Signal cancellation. Idempotent – safe to call multiple times."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """True if ``cancel()`` has been called at least once."""
        return self._event.is_set()

    def reset(self) -> None:
        """Clear the cancellation flag (for reuse in tests)."""
        self._event.clear()


class SessionContext:
    """Holds all mutable per-session state for the STT pipeline.

    Attributes:
        session_id: Non-empty string identifier for this session.
        confidence_threshold: Segments with confidence below this value are
            flagged as low-confidence.  Range [0.0, 1.0].  Default 0.0 means
            no threshold enforcement.
        cancellation_token: ``CancellationToken`` that callers can check or
            trigger to stop processing.
    """

    def __init__(
        self,
        session_id: str,
        confidence_threshold: float = 0.0,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        if not session_id or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if not (0.0 <= confidence_threshold <= 1.0):
            raise ValueError(
                f"confidence_threshold must be in [0.0, 1.0], got {confidence_threshold}"
            )
        self.session_id: str = session_id.strip()
        self.confidence_threshold: float = confidence_threshold
        self.cancellation_token: CancellationToken = (
            cancellation_token if cancellation_token is not None else CancellationToken()
        )

    @property
    def is_cancelled(self) -> bool:
        """Convenience shortcut to ``cancellation_token.is_cancelled``."""
        return self.cancellation_token.is_cancelled

    def cancel(self) -> None:
        """Cancel this session."""
        self.cancellation_token.cancel()


class SessionManager:
    """Thread-safe registry of active transcription sessions.

    Usage::

        manager = SessionManager()
        ctx = manager.create_session("sess_001", confidence_threshold=0.7)
        # ... later ...
        manager.cancel_session("sess_001")
        manager.remove_session("sess_001")
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionContext] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        session_id: str,
        confidence_threshold: float = 0.0,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> SessionContext:
        """Create and register a new session context.

        Args:
            session_id: Non-empty session identifier.
            confidence_threshold: Low-confidence threshold [0.0, 1.0].
            cancellation_token: Optional pre-existing token (created if not provided).

        Returns:
            The new ``SessionContext``.

        Raises:
            ValueError: If a session with the same ID already exists.
        """
        ctx = SessionContext(
            session_id=session_id,
            confidence_threshold=confidence_threshold,
            cancellation_token=cancellation_token,
        )
        with self._lock:
            if session_id in self._sessions:
                raise ValueError(f"Session '{session_id}' already exists.")
            self._sessions[session_id] = ctx
        return ctx

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Return the context for *session_id*, or ``None`` if not found."""
        with self._lock:
            return self._sessions.get(session_id)

    def cancel_session(self, session_id: str) -> bool:
        """Cancel the session identified by *session_id*.

        Returns:
            True if the session existed and was cancelled; False otherwise.
        """
        with self._lock:
            ctx = self._sessions.get(session_id)
        if ctx is not None:
            ctx.cancel()
            return True
        return False

    def remove_session(self, session_id: str) -> None:
        """Remove a session from the registry (call after it finishes)."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def active_sessions(self) -> Dict[str, SessionContext]:
        """Return a snapshot of the current session registry."""
        with self._lock:
            return dict(self._sessions)


__all__ = ["CancellationToken", "SessionContext", "SessionManager"]
