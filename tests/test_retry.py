"""Tests for sde4_stt.retry — timeout, bounded retries, error normalisation."""

import time
import pytest

from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.retry import NormalizedError, RetryableAdapter, RetryConfig
from sde4_stt.schemas.transcript import TranscriptEventType


# ---------------------------------------------------------------------------
# NormalizedError
# ---------------------------------------------------------------------------

class TestNormalizedError:

    def test_to_transcript_error(self):
        err = NormalizedError(
            code="TEST_CODE",
            message="something broke",
            recoverable=True,
            original=ValueError("bad"),
        )
        te = err.to_transcript_error()
        assert te.code == "TEST_CODE"
        assert te.message == "something broke"
        assert te.recoverable is True
        assert te.details["original_type"] == "ValueError"

    def test_without_original(self):
        err = NormalizedError(code="X", message="y")
        te = err.to_transcript_error()
        assert te.details is None

    def test_canonical_codes_exist(self):
        assert NormalizedError.TIMEOUT == "TIMEOUT"
        assert NormalizedError.PROVIDER_ERROR == "PROVIDER_ERROR"
        assert NormalizedError.INVALID_INPUT == "INVALID_INPUT"
        assert NormalizedError.UNKNOWN_ERROR == "UNKNOWN_ERROR"


# ---------------------------------------------------------------------------
# RetryableAdapter — happy path
# ---------------------------------------------------------------------------

class TestRetryableAdapterHappyPath:

    def test_wraps_adapter_name(self):
        inner = FakeTranscriber()
        wrapped = RetryableAdapter(inner)
        assert "retryable" in wrapped.provider_name

    def test_start_session_delegates(self):
        inner = FakeTranscriber(canned_transcript="hello world")
        wrapped = RetryableAdapter(inner)
        events = wrapped.start_session("s1")
        assert any(e.event_type == TranscriptEventType.START for e in events)
        assert wrapped.is_active

    def test_full_lifecycle_works(self):
        inner = FakeTranscriber(canned_transcript="hello world")
        wrapped = RetryableAdapter(inner)
        events = []
        events.extend(wrapped.start_session("s1"))
        events.extend(wrapped.process_chunk(b"\x00\x00" * 100))
        events.extend(wrapped.finish_session())
        types = [e.event_type for e in events]
        assert TranscriptEventType.START in types
        assert TranscriptEventType.COMPLETE in types


# ---------------------------------------------------------------------------
# RetryableAdapter — error normalisation
# ---------------------------------------------------------------------------

class TestErrorNormalisation:

    def test_normalize_value_error(self):
        inner = FakeTranscriber()
        wrapped = RetryableAdapter(inner)
        err = wrapped._normalize_error(ValueError("bad input"))
        assert err.code == NormalizedError.INVALID_INPUT
        assert err.recoverable is False

    def test_normalize_timeout_error(self):
        inner = FakeTranscriber()
        wrapped = RetryableAdapter(inner)
        err = wrapped._normalize_error(TimeoutError("slow"))
        assert err.code == NormalizedError.TIMEOUT
        assert err.recoverable is True

    def test_normalize_connection_error(self):
        inner = FakeTranscriber()
        wrapped = RetryableAdapter(inner)
        err = wrapped._normalize_error(ConnectionError("down"))
        assert err.code == NormalizedError.PROVIDER_ERROR
        assert err.recoverable is True

    def test_normalize_runtime_error(self):
        inner = FakeTranscriber()
        wrapped = RetryableAdapter(inner)
        err = wrapped._normalize_error(RuntimeError("crash"))
        assert err.code == NormalizedError.PROVIDER_ERROR
        assert err.recoverable is True

    def test_normalize_unknown_error(self):
        inner = FakeTranscriber()
        wrapped = RetryableAdapter(inner)
        err = wrapped._normalize_error(KeyError("wat"))
        assert err.code == NormalizedError.UNKNOWN_ERROR
        assert err.recoverable is False


# ---------------------------------------------------------------------------
# RetryableAdapter — retry behaviour
# ---------------------------------------------------------------------------

class _FailNTimesAdapter(FakeTranscriber):
    """Test adapter that raises on the first N calls to start_session."""

    def __init__(self, fail_count: int, exc: Exception):
        super().__init__(canned_transcript="test")
        self._fail_count = fail_count
        self._calls = 0
        self._exc = exc

    def start_session(self, session_id, language="en", sample_rate=16000):
        self._calls += 1
        if self._calls <= self._fail_count:
            raise self._exc
        return super().start_session(session_id, language, sample_rate)


class TestRetryBehaviour:

    def test_recoverable_error_retried(self):
        inner = _FailNTimesAdapter(2, RuntimeError("transient"))
        config = RetryConfig(max_retries=3, backoff_base_s=0.01)
        wrapped = RetryableAdapter(inner, config)
        events = wrapped.start_session("s1")
        # After 2 failures + 1 success = 3 calls total
        assert inner._calls == 3
        assert any(e.event_type == TranscriptEventType.START for e in events)

    def test_non_recoverable_error_not_retried(self):
        inner = _FailNTimesAdapter(5, ValueError("bad"))
        config = RetryConfig(max_retries=3, backoff_base_s=0.01)
        wrapped = RetryableAdapter(inner, config)
        events = wrapped.start_session("s1")
        # ValueError is not recoverable → should fail immediately after 1 call
        assert inner._calls == 1
        assert events[0].event_type == TranscriptEventType.ERROR
        assert events[0].error.code == NormalizedError.INVALID_INPUT

    def test_retries_exhausted_returns_error(self):
        inner = _FailNTimesAdapter(10, RuntimeError("always fails"))
        config = RetryConfig(max_retries=2, backoff_base_s=0.01)
        wrapped = RetryableAdapter(inner, config)
        events = wrapped.start_session("s1")
        # 1 initial + 2 retries = 3 calls, all fail
        assert inner._calls == 3
        assert events[0].event_type == TranscriptEventType.ERROR

    def test_error_event_has_valid_fields(self):
        inner = _FailNTimesAdapter(1, ValueError("oops"))
        config = RetryConfig(max_retries=0, backoff_base_s=0.01)
        wrapped = RetryableAdapter(inner, config)
        wrapped._session_id = "test_session"
        events = wrapped.start_session("test_session")
        err_event = events[0]
        assert err_event.event_type == TranscriptEventType.ERROR
        assert err_event.session_id == "test_session"
        assert err_event.error is not None
        assert err_event.error.code == NormalizedError.INVALID_INPUT

    def test_process_chunk_with_retry(self):
        """process_chunk also benefits from retry wrapping."""
        inner = FakeTranscriber(canned_transcript="hello")
        config = RetryConfig(max_retries=1, backoff_base_s=0.01)
        wrapped = RetryableAdapter(inner, config)
        wrapped.start_session("s1")
        # Normal chunk processing should work
        events = wrapped.process_chunk(b"\x00\x00" * 100)
        # Should produce INTERIM or FINAL events, not errors
        assert all(e.event_type != TranscriptEventType.ERROR for e in events)


# ---------------------------------------------------------------------------
# RetryConfig
# ---------------------------------------------------------------------------

class TestRetryConfig:

    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.timeout_s == 30.0
        assert cfg.backoff_base_s == 0.5
        assert cfg.backoff_factor == 2.0

    def test_custom_values(self):
        cfg = RetryConfig(max_retries=1, timeout_s=5.0, backoff_base_s=0.1, backoff_factor=3.0)
        assert cfg.max_retries == 1
        assert cfg.timeout_s == 5.0

    def test_frozen(self):
        cfg = RetryConfig()
        with pytest.raises(AttributeError):
            cfg.max_retries = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Genuine Timeout Enforcement Tests
# ---------------------------------------------------------------------------

class _SlowAdapter(FakeTranscriber):
    """Adapter that sleeps during start_session to simulate slow operations."""

    def __init__(self, delay_s: float, succeed_after_attempts: int = 1):
        super().__init__(canned_transcript="slow")
        self.delay_s = delay_s
        self.succeed_after_attempts = succeed_after_attempts
        self.attempts = 0

    def start_session(self, session_id, language="en", sample_rate=16000):
        self.attempts += 1
        time.sleep(self.delay_s)
        if self.attempts < self.succeed_after_attempts:
            raise TimeoutError("slow provider network response")
        return super().start_session(session_id, language, sample_rate)


class TestTimeoutEnforcement:

    def test_operation_completing_before_timeout(self):
        """Fast operation completes successfully well before timeout."""
        inner = _SlowAdapter(delay_s=0.01)
        cfg = RetryConfig(max_retries=1, timeout_s=1.0, per_attempt_timeout_s=0.5)
        wrapped = RetryableAdapter(inner, cfg)
        try:
            events = wrapped.start_session("s_fast")
            assert any(e.event_type == TranscriptEventType.START for e in events)
            assert inner.attempts == 1
        finally:
            wrapped.close()

    def test_operation_exceeding_timeout(self):
        """Operation exceeding per-attempt timeout raises a normalized TIMEOUT error."""
        inner = _SlowAdapter(delay_s=0.25)
        cfg = RetryConfig(max_retries=0, timeout_s=1.0, per_attempt_timeout_s=0.05)
        wrapped = RetryableAdapter(inner, cfg)
        try:
            events = wrapped.start_session("s_slow")
            assert len(events) == 1
            assert events[0].event_type == TranscriptEventType.ERROR
            assert events[0].error.code == NormalizedError.TIMEOUT
            assert "timed out after" in events[0].error.message
        finally:
            wrapped.close()

    def test_timeout_followed_by_retry(self):
        """Attempt 1 times out, attempt 2 succeeds."""
        inner = _SlowAdapter(delay_s=0.02, succeed_after_attempts=2)
        cfg = RetryConfig(
            max_retries=2,
            timeout_s=2.0,
            backoff_base_s=0.01,
            per_attempt_timeout_s=0.5,
        )
        wrapped = RetryableAdapter(inner, cfg)
        try:
            events = wrapped.start_session("s_retry")
            assert any(e.event_type == TranscriptEventType.START for e in events)
            assert inner.attempts == 2
        finally:
            wrapped.close()

    def test_overall_retry_deadline_exceeded(self):
        """When cumulative deadline is exceeded, further retries are prevented."""
        inner = _SlowAdapter(delay_s=0.08, succeed_after_attempts=10)
        cfg = RetryConfig(
            max_retries=5,
            timeout_s=0.10,  # overall deadline 100ms
            backoff_base_s=0.05,
            per_attempt_timeout_s=0.08,
        )
        wrapped = RetryableAdapter(inner, cfg)
        try:
            events = wrapped.start_session("s_deadline")
            assert len(events) == 1
            assert events[0].event_type == TranscriptEventType.ERROR
            assert events[0].error.code == NormalizedError.TIMEOUT
            assert "deadline" in events[0].error.message.lower()
            # Must not have executed all 6 attempts because deadline expired
            assert inner.attempts < 5
        finally:
            wrapped.close()

    def test_non_retryable_error_aborts_immediately(self):
        """Non-recoverable errors (e.g. ValueError) fail on first attempt without retry."""
        inner = _FailNTimesAdapter(fail_count=3, exc=ValueError("unrecoverable argument"))
        cfg = RetryConfig(max_retries=3, timeout_s=5.0)
        wrapped = RetryableAdapter(inner, cfg)
        try:
            events = wrapped.start_session("s_fail")
            assert len(events) == 1
            assert events[0].event_type == TranscriptEventType.ERROR
            assert events[0].error.code == NormalizedError.INVALID_INPUT
            assert inner._calls == 1
        finally:
            wrapped.close()

    def test_cleanup_after_timeout(self):
        """Verify close() shuts down executor and cleans up cleanly."""
        inner = _SlowAdapter(delay_s=0.01)
        wrapped = RetryableAdapter(inner)
        wrapped.start_session("s_clean")
        assert wrapped._executor is not None
        wrapped.close()
        assert wrapped._executor is None


