"""
Retry, Timeout, and Error Normalization for STT Adapters.

Provides resilient execution of transcription operations by wrapping any
``BaseTranscriberAdapter`` with configurable retry logic, exponential backoff,
genuine per-operation timeouts, deadline enforcement, and consistent error normalization.

Key components:
    - ``RetryConfig``: Immutable configuration for retry and timeout behaviour.
    - ``NormalizedError``: Exception that maps provider-specific failures to
      standard error codes and converts to ``TranscriptError``.
    - ``RetryableAdapter``: Decorator adapter that adds retry/timeout semantics
      to any concrete ``BaseTranscriberAdapter`` implementation.

Synchronous Provider Timeout Contract & Limitations:
-----------------------------------------------------
In Python, synchronous native provider calls (e.g. C-level audio libraries or network
drivers that block without checking GIL state) cannot be forcefully killed without
corrupting process state. ``RetryableAdapter`` enforces operation timeouts by dispatching
attempts to a managed worker thread and awaiting completion via `concurrent.futures.Future.result(timeout=...)`.
When an attempt exceeds its allocated timeout:
1. A ``TimeoutError`` is raised immediately to the caller / pipeline.
2. The timed-out attempt is abandoned/detached; unmanaged threads are never leaked.
3. The overall deadline is strictly enforced before and during retries.
4. Backoff pauses that would exceed the overall deadline are prevented.
"""

from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Union

from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.schemas.transcript import (
    TranscriptError,
    TranscriptEvent,
    TranscriptEventType,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RetryConfig:
    """Immutable configuration controlling retry and timeout behaviour.

    Attributes:
        max_retries: Maximum number of retry attempts after the initial try.
        timeout_s: Maximum cumulative wall-clock time (seconds) for a single
            operation including all retries before a timeout error is raised.
        backoff_base_s: Initial backoff wait in seconds before the first retry.
        backoff_factor: Multiplicative factor applied to the backoff wait after
            each successive retry (exponential backoff).
        per_attempt_timeout_s: Optional maximum duration (seconds) for an individual
            attempt. If None, bounded only by the remaining cumulative timeout_s.
        enforce_execution_timeout: Whether to enforce hard operation timeouts via
            worker execution. Default True.
    """

    max_retries: int = 3
    timeout_s: float = 30.0
    backoff_base_s: float = 0.5
    backoff_factor: float = 2.0
    per_attempt_timeout_s: Optional[float] = None
    enforce_execution_timeout: bool = True

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {self.max_retries}")
        if self.timeout_s <= 0:
            raise ValueError(f"timeout_s must be positive, got {self.timeout_s}")
        if self.backoff_base_s < 0:
            raise ValueError(f"backoff_base_s must be non-negative, got {self.backoff_base_s}")
        if self.backoff_factor < 1.0:
            raise ValueError(f"backoff_factor must be >= 1.0, got {self.backoff_factor}")
        if self.per_attempt_timeout_s is not None and self.per_attempt_timeout_s <= 0:
            raise ValueError(f"per_attempt_timeout_s must be positive, got {self.per_attempt_timeout_s}")


# ---------------------------------------------------------------------------
# Normalized Error
# ---------------------------------------------------------------------------

class NormalizedError(Exception):
    """Provider-agnostic exception with a machine-readable error code.

    Wraps an optional ``original`` exception and carries enough context to be
    converted into a ``TranscriptError`` for inclusion in error events.

    Class-level constants define the canonical error codes used across the
    retry/timeout layer.
    """

    # Canonical error codes
    TIMEOUT: str = "TIMEOUT"
    PROVIDER_ERROR: str = "PROVIDER_ERROR"
    INVALID_INPUT: str = "INVALID_INPUT"
    UNKNOWN_ERROR: str = "UNKNOWN_ERROR"

    def __init__(
        self,
        code: str,
        message: str,
        recoverable: bool = False,
        original: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.recoverable = recoverable
        self.original = original

    def to_transcript_error(self) -> TranscriptError:
        """Convert this normalised error into a ``TranscriptError`` schema object.

        Returns:
            A frozen ``TranscriptError`` Pydantic model carrying the same code,
            message, and recoverability flag, with optional details about the
            original exception.
        """
        details: Optional[dict] = None
        if self.original is not None:
            details = {
                "original_type": type(self.original).__name__,
                "original_message": str(self.original),
            }
        return TranscriptError(
            code=self.code,
            message=self.message,
            recoverable=self.recoverable,
            details=details,
        )


# ---------------------------------------------------------------------------
# Retryable Adapter
# ---------------------------------------------------------------------------

class RetryableAdapter(BaseTranscriberAdapter):
    """Decorator adapter that adds retry, timeout, and error-handling semantics.

    Wraps any concrete ``BaseTranscriberAdapter`` and delegates every lifecycle
    call (``start_session``, ``process_chunk``, ``finish_session``) through
    ``_with_retry``, which applies genuine execution timeouts, exponential backoff,
    and cumulative deadline checking.

    Args:
        adapter: The inner ``BaseTranscriberAdapter`` to wrap.
        config: Optional ``RetryConfig``; defaults to ``RetryConfig()`` when
            not supplied.
    """

    def __init__(
        self,
        adapter: BaseTranscriberAdapter,
        config: Optional[RetryConfig] = None,
    ) -> None:
        super().__init__(adapter.provider_name + "-retryable")
        self._inner = adapter
        self._config = config if config is not None else RetryConfig()
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None

    def _get_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        """Lazily initialize a bounded managed worker thread pool."""
        if self._executor is None:
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix=f"stt-retry-{self.provider_name}",
            )
        return self._executor

    def close(self) -> None:
        """Shut down resources and managed thread pool."""
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        if hasattr(self._inner, "close") and callable(self._inner.close):
            try:
                self._inner.close()
            except Exception:
                pass

    def __enter__(self) -> "RetryableAdapter":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    # -- Public lifecycle methods -------------------------------------------

    def start_session(
        self,
        session_id: str,
        language: str = "en",
        sample_rate: int = 16000,
    ) -> List[TranscriptEvent]:
        """Start a transcription session on the inner adapter with retry logic."""
        self._session_id = session_id

        def _fn() -> List[TranscriptEvent]:
            return self._inner.start_session(session_id, language, sample_rate)

        events = self._with_retry("start_session", _fn)

        # Mirror inner adapter's active state on success
        if not any(e.event_type == TranscriptEventType.ERROR for e in events):
            self._is_active = True

        return events

    def process_chunk(
        self,
        chunk: Union[object, bytes],
        is_last: bool = False,
    ) -> List[TranscriptEvent]:
        """Process a single audio chunk through the inner adapter with retry logic."""

        def _fn() -> List[TranscriptEvent]:
            try:
                return self._inner.process_chunk(chunk, is_last=is_last)
            except TypeError:
                return self._inner.process_chunk(chunk)

        return self._with_retry("process_chunk", _fn)

    def finish_session(self) -> List[TranscriptEvent]:
        """Finalise the transcription session on the inner adapter with retry logic."""

        def _fn() -> List[TranscriptEvent]:
            return self._inner.finish_session()

        events = self._with_retry("finish_session", _fn)

        # Clear active state on success
        if not any(e.event_type == TranscriptEventType.ERROR for e in events):
            self._is_active = False

        return events

    # -- Private helpers ----------------------------------------------------

    def _with_retry(
        self,
        operation_name: str,
        fn: Callable[[], List[TranscriptEvent]],
    ) -> List[TranscriptEvent]:
        """Execute *fn* with genuine timeout enforcement, retry, and backoff."""
        config = self._config
        max_attempts = 1 + config.max_retries
        start_time = time.monotonic()
        last_error: Optional[NormalizedError] = None

        for attempt in range(max_attempts):
            elapsed = time.monotonic() - start_time
            remaining_deadline = config.timeout_s - elapsed

            # Check overall deadline before attempt
            if remaining_deadline <= 0:
                timeout_err = NormalizedError(
                    code=NormalizedError.TIMEOUT,
                    message=(
                        f"Operation '{operation_name}' exceeded overall retry deadline "
                        f"({config.timeout_s:.2f}s) after {elapsed:.2f}s"
                    ),
                    recoverable=False,
                    original=last_error.original if last_error else None,
                )
                return [self._make_error_event(timeout_err, operation_name)]

            # Calculate attempt-specific timeout
            if config.per_attempt_timeout_s is not None:
                attempt_timeout = min(remaining_deadline, config.per_attempt_timeout_s)
            else:
                attempt_timeout = remaining_deadline

            try:
                if config.enforce_execution_timeout and attempt_timeout > 0:
                    executor = self._get_executor()
                    future = executor.submit(fn)
                    try:
                        return future.result(timeout=max(0.001, attempt_timeout))
                    except concurrent.futures.TimeoutError as te:
                        future.cancel()
                        raise TimeoutError(
                            f"Operation '{operation_name}' timed out after {attempt_timeout:.2f}s"
                        ) from te
                else:
                    return fn()

            except Exception as exc:
                last_error = self._normalize_error(exc)

                # Non-recoverable -> fail immediately
                if not last_error.recoverable:
                    return [self._make_error_event(last_error, operation_name)]

                # Recoverable but retries exhausted -> fail
                if attempt >= max_attempts - 1:
                    return [self._make_error_event(last_error, operation_name)]

                # Check if backoff sleep would violate overall deadline
                backoff = config.backoff_base_s * (config.backoff_factor ** attempt)
                now_elapsed = time.monotonic() - start_time
                if now_elapsed + backoff >= config.timeout_s:
                    deadline_err = NormalizedError(
                        code=NormalizedError.TIMEOUT,
                        message=(
                            f"Overall retry deadline ({config.timeout_s:.2f}s) exceeded: "
                            f"next retry requires {backoff:.2f}s backoff but only "
                            f"{max(0.0, config.timeout_s - now_elapsed):.2f}s remain"
                        ),
                        recoverable=False,
                        original=last_error.original if last_error else None,
                    )
                    return [self._make_error_event(deadline_err, operation_name)]

                time.sleep(backoff)

        # Defensive fallback
        assert last_error is not None  # noqa: S101
        return [self._make_error_event(last_error, operation_name)]

    def _normalize_error(self, exc: Exception) -> NormalizedError:
        """Map a raw exception to a ``NormalizedError`` with a canonical code."""
        if isinstance(exc, TimeoutError):
            return NormalizedError(
                code=NormalizedError.TIMEOUT,
                message=f"Timeout: {exc}",
                recoverable=True,
                original=exc,
            )
        if isinstance(exc, ConnectionError):
            return NormalizedError(
                code=NormalizedError.PROVIDER_ERROR,
                message=f"Connection error: {exc}",
                recoverable=True,
                original=exc,
            )
        if isinstance(exc, ValueError):
            return NormalizedError(
                code=NormalizedError.INVALID_INPUT,
                message=f"Invalid input: {exc}",
                recoverable=False,
                original=exc,
            )
        if isinstance(exc, RuntimeError):
            return NormalizedError(
                code=NormalizedError.PROVIDER_ERROR,
                message=f"Runtime error: {exc}",
                recoverable=True,
                original=exc,
            )
        return NormalizedError(
            code=NormalizedError.UNKNOWN_ERROR,
            message=f"Unexpected error: {exc}",
            recoverable=False,
            original=exc,
        )

    def _make_error_event(
        self,
        error: NormalizedError,
        operation: str,
    ) -> TranscriptEvent:
        """Build an ERROR ``TranscriptEvent`` from a ``NormalizedError``."""
        return TranscriptEvent(
            event_id=f"evt_error_{operation}_{time.monotonic()}",
            session_id=self._session_id or "unknown",
            event_type=TranscriptEventType.ERROR,
            timestamp=time.time(),
            error=error.to_transcript_error(),
        )


__all__ = ["RetryConfig", "NormalizedError", "RetryableAdapter"]
