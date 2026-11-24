"""
Automatic Fallback Adapter for Speech-to-Text (Week 3, D17-18).

``FallbackAdapter`` wraps a primary ``BaseTranscriberAdapter`` and transparently
falls back to the ``FakeTranscriber`` (or any secondary adapter) when the primary
encounters a *recoverable* failure (network errors, quota exhaustion, rate limiting).

Design decisions:
    - Non-recoverable errors are propagated as ERROR events, never swallowed.
    - Fallback preserves session_id and all relevant metadata.
    - Fallback cannot loop: once fallback is active, further recoverable errors from
      the fallback produce ERROR events (no infinite retry/fallback chain).
    - Cancellation of one session does not affect other sessions.
    - The module never imports RealSpeechTranscriber.
"""

from __future__ import annotations

import time
from typing import List, Optional, Union

from academia_audio.schemas import AudioChunk

from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.logging import get_logger, log_fallback_event
from sde4_stt.retry import NormalizedError
from sde4_stt.schemas.transcript import (
    TranscriptError,
    TranscriptEvent,
    TranscriptEventType,
)

# Error codes that trigger fallback
_RECOVERABLE_FALLBACK_CODES = {
    NormalizedError.NETWORK_ERROR,
    NormalizedError.QUOTA_EXHAUSTED,
    NormalizedError.RATE_LIMITED,
    NormalizedError.PROVIDER_ERROR,
    NormalizedError.TIMEOUT,
}


def _is_recoverable_exception(exc: Exception) -> bool:
    """Return True if an unhandled exception represents a recoverable failure."""
    if isinstance(exc, (ConnectionError, OSError, TimeoutError, PermissionError)):
        return True
    if isinstance(exc, NormalizedError):
        return exc.recoverable
    err_str = (str(exc) + " " + type(exc).__name__).lower()
    if any(k in err_str for k in ("quota", "rate limit", "429", "timeout", "network", "connection", "unavailable")):
        return True
    return False


def _is_recoverable_error_event(event: TranscriptEvent) -> bool:
    """Return True if the event is a recoverable ERROR that should trigger fallback."""
    return (
        event.event_type == TranscriptEventType.ERROR
        and event.error is not None
        and event.error.recoverable
        and event.error.code in _RECOVERABLE_FALLBACK_CODES
    )


class FallbackAdapter(BaseTranscriberAdapter):
    """STT adapter that falls back to a mock provider on recoverable failures.

    Args:
        primary: The primary adapter to try first.
        fallback: The fallback adapter.  Defaults to ``FakeTranscriber()`` when
            not provided.

    Usage::

        primary = SomePaidAdapter(...)
        adapter = FallbackAdapter(primary=primary)
        for event in adapter.transcribe_stream(chunks, session_id="s1"):
            print(event)
    """

    def __init__(
        self,
        primary: BaseTranscriberAdapter,
        fallback: Optional[BaseTranscriberAdapter] = None,
    ) -> None:
        super().__init__(provider_name=f"fallback({primary.provider_name})")
        self._primary = primary
        self._fallback: BaseTranscriberAdapter = (
            fallback if fallback is not None else FakeTranscriber()
        )
        self._using_fallback: bool = False
        self._language: str = "en"
        self._sample_rate: int = 16000
        self._buffered_chunks: List[tuple] = []
        self._logger = get_logger("sde4_stt.fallback")

    @property
    def using_fallback(self) -> bool:
        """True if the fallback provider is currently active."""
        return self._using_fallback

    def start_session(
        self,
        session_id: str,
        language: str = "en",
        sample_rate: int = 16000,
    ) -> List[TranscriptEvent]:
        """Start session on primary; switch to fallback on recoverable failure."""
        self._session_id = session_id
        self._language = language
        self._sample_rate = sample_rate
        self._using_fallback = False
        self._buffered_chunks = []

        try:
            events = self._primary.start_session(session_id, language, sample_rate)
        except Exception as exc:
            if _is_recoverable_exception(exc):
                err_event = self._make_error_event(str(exc), recoverable=True)
                events = [err_event]
            else:
                return [self._make_error_event(str(exc), recoverable=False)]

        fallback_events = self._check_and_activate_fallback(events, "start_session")
        if fallback_events is not None:
            self._is_active = True
            return fallback_events

        self._is_active = True
        return events

    def process_chunk(
        self,
        chunk: Union[AudioChunk, bytes],
        is_last: bool = False,
    ) -> List[TranscriptEvent]:
        """Process chunk on the active provider (primary or fallback)."""
        if not self._using_fallback:
            self._buffered_chunks.append((chunk, is_last))

        active = self._fallback if self._using_fallback else self._primary

        try:
            try:
                events = active.process_chunk(chunk, is_last=is_last)
            except TypeError:
                events = active.process_chunk(chunk)
        except Exception as exc:
            if not self._using_fallback and _is_recoverable_exception(exc):
                events = [self._make_error_event(str(exc), recoverable=True)]
            else:
                return [self._make_error_event(str(exc), recoverable=False)]

        if self._using_fallback:
            # If fallback itself fails, return error – no further recursion
            return events

        fallback_events = self._check_and_activate_fallback(events, "process_chunk")
        if fallback_events is not None:
            # Replay prior chunks through fallback, then current chunk
            try:
                for ch, last in self._buffered_chunks[:-1]:
                    try:
                        self._fallback.process_chunk(ch, is_last=last)
                    except TypeError:
                        self._fallback.process_chunk(ch)
                try:
                    extra = self._fallback.process_chunk(chunk, is_last=is_last)
                except TypeError:
                    extra = self._fallback.process_chunk(chunk)
                return fallback_events + extra
            except Exception as exc:
                return fallback_events + [
                    self._make_error_event(str(exc), recoverable=False)
                ]

        return events

    def finish_session(self) -> List[TranscriptEvent]:
        """Finish session on the active provider."""
        active = self._fallback if self._using_fallback else self._primary
        try:
            events = active.finish_session()
        except Exception as exc:
            if not self._using_fallback and _is_recoverable_exception(exc):
                events = [self._make_error_event(str(exc), recoverable=True)]
            else:
                events = [self._make_error_event(str(exc), recoverable=False)]

        if self._using_fallback:
            self._is_active = False
            return events

        fallback_events = self._check_and_activate_fallback(events, "finish_session")
        if fallback_events is not None:
            # Replay all buffered chunks through fallback and finish session
            try:
                replayed_events: List[TranscriptEvent] = []
                for ch, last in self._buffered_chunks:
                    try:
                        chunk_evts = self._fallback.process_chunk(ch, is_last=last)
                    except TypeError:
                        chunk_evts = self._fallback.process_chunk(ch)
                    if chunk_evts:
                        replayed_events.extend(chunk_evts)
                fin = self._fallback.finish_session()
                self._is_active = False
                return fallback_events + replayed_events + fin
            except Exception as exc:
                self._is_active = False
                return fallback_events + [
                    self._make_error_event(str(exc), recoverable=False)
                ]

        self._is_active = False
        return events

    def cancel(self) -> List[TranscriptEvent]:
        """Cancel the active provider session."""
        active = self._fallback if self._using_fallback else self._primary
        events = active.cancel()
        self._is_active = False
        return events

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_and_activate_fallback(
        self,
        events: List[TranscriptEvent],
        operation: str,
    ) -> Optional[List[TranscriptEvent]]:
        """If *events* contain a recoverable error, activate fallback.

        Returns:
            Replacement events (notification + fallback start) if fallback was
            activated; ``None`` otherwise.
        """
        if not any(_is_recoverable_error_event(e) for e in events):
            return None

        self._using_fallback = True
        log_fallback_event(
            self._logger,
            self._session_id or "unknown",
            self._primary.provider_name,
            self._fallback.provider_name,
            f"Operation {operation} triggered fallback",
        )

        # Emit a normalized notification that fallback was activated
        notification = TranscriptEvent(
            event_id=f"evt_{self._session_id}_fallback_{operation}_{time.monotonic()}",
            session_id=self._session_id or "unknown",
            event_type=TranscriptEventType.ERROR,
            timestamp=time.time(),
            error=TranscriptError(
                code="FALLBACK_ACTIVATED",
                message=(
                    f"Primary provider failed during '{operation}'. "
                    f"Switching to fallback provider '{self._fallback.provider_name}'."
                ),
                recoverable=True,
                details={"primary": self._primary.provider_name,
                         "fallback": self._fallback.provider_name},
            ),
        )

        # Start fallback session with the same session_id
        try:
            fallback_start = self._fallback.start_session(
                self._session_id or "unknown",
                self._language,
                self._sample_rate,
            )
        except Exception as exc:
            fallback_start = [self._make_error_event(str(exc), recoverable=False)]

        return [notification] + fallback_start

    def _make_error_event(
        self,
        message: str,
        recoverable: bool,
        code: Optional[str] = None,
    ) -> TranscriptEvent:
        if code is None:
            msg_lower = message.lower()
            if "quota" in msg_lower:
                code = NormalizedError.QUOTA_EXHAUSTED
            elif "rate limit" in msg_lower or "429" in msg_lower:
                code = NormalizedError.RATE_LIMITED
            elif "timeout" in msg_lower:
                code = NormalizedError.TIMEOUT
            elif "network" in msg_lower or "connection" in msg_lower:
                code = NormalizedError.NETWORK_ERROR
            else:
                code = NormalizedError.PROVIDER_ERROR

        return TranscriptEvent(
            event_id=f"evt_{self._session_id}_err_{time.monotonic()}",
            session_id=self._session_id or "unknown",
            event_type=TranscriptEventType.ERROR,
            timestamp=time.time(),
            error=TranscriptError(
                code=code,
                message=message,
                recoverable=recoverable,
            ),
        )


__all__ = ["FallbackAdapter"]
