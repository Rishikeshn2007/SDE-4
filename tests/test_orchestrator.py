"""Tests for sde4_stt.orchestrator — end-to-end contract tests."""

import pytest

from academia_audio.schemas import AudioChunk, AudioFormat
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.dedup import EventDeduplicator
from sde4_stt.orchestrator import TranscriptionOrchestrator, TranscriptionResult
from sde4_stt.preprocessing import AudioPreprocessor
from sde4_stt.retry import RetryConfig
from sde4_stt.schemas.transcript import TranscriptEventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_w1_chunks(n: int = 3, sample_rate: int = 16000) -> list[AudioChunk]:
    """Create *n* valid W1 AudioChunks with deterministic PCM data."""
    fmt = AudioFormat(sample_rate=sample_rate, channels=1)
    frame_size = fmt.frame_size
    chunk_frames = 160  # 10 ms at 16 kHz
    chunk_bytes = b"\x00\x00" * chunk_frames
    return [
        AudioChunk(
            sequence_id=i,
            timestamp_s=i * (chunk_frames / sample_rate),
            format=fmt,
            data=chunk_bytes,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# End-to-end: chunk → transcript in mock mode
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """Acceptance criterion: chunk-to-transcript works end-to-end in mock mode."""

    def test_basic_transcription(self):
        adapter = FakeTranscriber(canned_transcript="hello world test")
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(3)
        result = orch.transcribe(chunks, session_id="test1")
        assert isinstance(result, TranscriptionResult)
        assert result.session_id == "test1"
        assert result.chunks_processed == 3
        assert len(result.segments) >= 1

    def test_full_text_property(self):
        adapter = FakeTranscriber(canned_transcript="hello world test")
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(3)
        result = orch.transcribe(chunks, session_id="test2")
        assert len(result.full_text) > 0

    def test_default_adapter_is_fake(self):
        orch = TranscriptionOrchestrator()
        chunks = _make_w1_chunks(2)
        result = orch.transcribe(chunks, session_id="test3")
        assert result.chunks_processed == 2
        # Should not have errors since fake transcriber is deterministic
        assert not result.has_errors

    def test_no_real_provider_needed(self):
        """Contract: default path needs no real provider or API key."""
        orch = TranscriptionOrchestrator()
        chunks = _make_w1_chunks(1)
        result = orch.transcribe(chunks, session_id="no_api_key")
        assert not result.has_errors


# ---------------------------------------------------------------------------
# With preprocessing
# ---------------------------------------------------------------------------

class TestWithPreprocessing:
    """Acceptance criterion: resampling and normalisation are tested."""

    def test_preprocessing_applied(self):
        adapter = FakeTranscriber(canned_transcript="preprocessed audio")
        pre = AudioPreprocessor(target_sample_rate=16000, normalize_audio=True)
        orch = TranscriptionOrchestrator(adapter=adapter, preprocessor=pre)
        chunks = _make_w1_chunks(2)
        result = orch.transcribe(chunks, session_id="pre1")
        assert result.chunks_processed == 2
        assert not result.has_errors

    def test_resampling_48k_to_16k(self):
        """Chunks at 48 kHz are resampled to 16 kHz before reaching the adapter."""
        adapter = FakeTranscriber(canned_transcript="resampled audio")
        pre = AudioPreprocessor(target_sample_rate=16000, normalize_audio=False)
        orch = TranscriptionOrchestrator(adapter=adapter, preprocessor=pre)
        # 48 kHz chunks
        chunks = _make_w1_chunks(2, sample_rate=48000)
        result = orch.transcribe(chunks, session_id="resample1")
        assert not result.has_errors
        assert result.chunks_processed == 2


# ---------------------------------------------------------------------------
# With retry config
# ---------------------------------------------------------------------------

class TestWithRetry:
    """Acceptance criterion: timeouts and bounded retries work."""

    def test_retry_wrapping_transparent(self):
        adapter = FakeTranscriber(canned_transcript="retry test")
        config = RetryConfig(max_retries=2, backoff_base_s=0.01)
        orch = TranscriptionOrchestrator(adapter=adapter, retry_config=config)
        chunks = _make_w1_chunks(2)
        result = orch.transcribe(chunks, session_id="retry1")
        assert not result.has_errors
        assert "retryable" in orch.adapter.provider_name


# ---------------------------------------------------------------------------
# Deduplication integration
# ---------------------------------------------------------------------------

class TestDedupIntegration:
    """Acceptance criterion: out-of-order and duplicate segments handled."""

    def test_no_duplicate_events_in_output(self):
        adapter = FakeTranscriber(canned_transcript="dedup test")
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(3)
        result = orch.transcribe(chunks, session_id="dedup1")
        event_ids = [e.event_id for e in result.events]
        assert len(event_ids) == len(set(event_ids))  # all unique


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Acceptance criterion: provider errors are normalised."""

    def test_simulated_error_captured(self):
        adapter = FakeTranscriber(
            canned_transcript="error test",
            fail_at_chunk_index=1,
        )
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(3)
        result = orch.transcribe(chunks, session_id="err1")
        assert result.has_errors

    def test_error_events_have_error_payload(self):
        adapter = FakeTranscriber(
            canned_transcript="error test",
            fail_at_chunk_index=0,
        )
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(2)
        result = orch.transcribe(chunks, session_id="err2")
        error_events = [
            e for e in result.events
            if e.event_type == TranscriptEventType.ERROR
        ]
        assert len(error_events) >= 1
        assert error_events[0].error is not None
        assert error_events[0].error.code  # has a code


# ---------------------------------------------------------------------------
# Contract tests — adapter interface
# ---------------------------------------------------------------------------

class TestAdapterContract:
    """Contract tests verifying the adapter lifecycle."""

    def test_lifecycle_event_types(self):
        """Every transcription produces START and COMPLETE events."""
        adapter = FakeTranscriber(canned_transcript="contract")
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(2)
        result = orch.transcribe(chunks, session_id="contract1")
        types = {e.event_type for e in result.events}
        assert TranscriptEventType.START in types
        assert TranscriptEventType.COMPLETE in types

    def test_final_segments_have_is_final_true(self):
        adapter = FakeTranscriber(canned_transcript="final check")
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(2)
        result = orch.transcribe(chunks, session_id="contract2")
        for seg in result.segments:
            assert seg.is_final is True

    def test_segments_sorted_by_sequence_number(self):
        adapter = FakeTranscriber(canned_transcript="ordering check")
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(3)
        result = orch.transcribe(chunks, session_id="contract3")
        seq_nums = [s.sequence_number for s in result.segments]
        assert seq_nums == sorted(seq_nums)

    def test_deterministic_output(self):
        """Same input → identical output (determinism check)."""
        adapter1 = FakeTranscriber(canned_transcript="deterministic")
        adapter2 = FakeTranscriber(canned_transcript="deterministic")
        orch1 = TranscriptionOrchestrator(adapter=adapter1)
        orch2 = TranscriptionOrchestrator(adapter=adapter2)
        chunks = _make_w1_chunks(2)
        r1 = orch1.transcribe(list(chunks), session_id="det1")
        r2 = orch2.transcribe(list(chunks), session_id="det1")
        assert r1.full_text == r2.full_text
        assert len(r1.segments) == len(r2.segments)

    def test_result_duration_positive(self):
        orch = TranscriptionOrchestrator()
        chunks = _make_w1_chunks(2)
        result = orch.transcribe(chunks, session_id="dur1")
        assert result.duration_s >= 0.0


# ---------------------------------------------------------------------------
# Robust Exception Boundaries & Failure Injection Tests
# ---------------------------------------------------------------------------

class _FailingAdapter(FakeTranscriber):
    """Adapter supporting failure injection at start, process, or finish."""

    def __init__(self, fail_at_start: bool = False, fail_at_finish: bool = False):
        super().__init__(canned_transcript="failing adapter")
        self.fail_at_start = fail_at_start
        self.fail_at_finish = fail_at_finish
        self.cleanup_called = False

    def start_session(self, session_id, language="en", sample_rate=16000):
        if self.fail_at_start:
            raise ConnectionError("Simulated network failure on start")
        return super().start_session(session_id, language, sample_rate)

    def finish_session(self):
        if self.fail_at_finish:
            raise RuntimeError("Simulated crash on session finalization")
        return super().finish_session()

    def close(self):
        self.cleanup_called = True


class TestOrchestratorExceptionBoundaries:
    """Tests verifying orchestrator exception boundaries and error normalization."""

    def test_invalid_session_parameters(self):
        """Invalid or empty session_id produces normalized ERROR event and empty segments."""
        orch = TranscriptionOrchestrator()
        chunks = _make_w1_chunks(1)

        for bad_id in ["", "   ", None]:  # type: ignore
            res = orch.transcribe(chunks, session_id=bad_id)
            assert res.has_errors
            assert res.segments == []
            err_events = [e for e in res.events if e.event_type == TranscriptEventType.ERROR]
            assert len(err_events) == 1
            assert err_events[0].error.code == "INVALID_SESSION_PARAMS"

    def test_audio_generator_failure_normalized(self):
        """Failing chunk generator is caught and normalized without unhandled exception."""
        def faulty_generator():
            yield _make_w1_chunks(1)[0]
            raise IOError("Microphone device disconnected abruptly")

        orch = TranscriptionOrchestrator()
        res = orch.transcribe(faulty_generator(), session_id="faulty_gen")
        assert res.has_errors
        assert res.segments == []
        err_events = [e for e in res.events if e.event_type == TranscriptEventType.ERROR]
        assert len(err_events) == 1
        assert err_events[0].error.code == "AUDIO_GENERATOR_FAILED"
        assert "Microphone device disconnected" in err_events[0].error.message

    def test_adapter_start_session_failure(self):
        """Adapter failing during start_session is caught and normalized."""
        adapter = _FailingAdapter(fail_at_start=True)
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(2)
        res = orch.transcribe(chunks, session_id="err_start")
        assert res.has_errors
        assert res.segments == []
        err_events = [e for e in res.events if e.event_type == TranscriptEventType.ERROR]
        assert len(err_events) == 1
        assert err_events[0].error.code == "START_SESSION_FAILED"

    def test_adapter_finish_session_failure(self):
        """Adapter failing during finish_session is caught and normalized."""
        adapter = _FailingAdapter(fail_at_finish=True)
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(2)
        res = orch.transcribe(chunks, session_id="err_finish")
        assert res.has_errors
        assert res.segments == []
        err_events = [e for e in res.events if e.event_type == TranscriptEventType.ERROR]
        assert any(e.error.code == "FINISH_SESSION_FAILED" for e in err_events)

    def test_preprocessing_failure_normalized(self):
        """Preprocessing failure on chunk is caught and normalized."""
        class _FailingPreprocessor(AudioPreprocessor):
            def process_chunk(self, chunk):
                raise ValueError("Corrupt audio frame header")

        orch = TranscriptionOrchestrator(preprocessor=_FailingPreprocessor())
        chunks = _make_w1_chunks(2)
        res = orch.transcribe(chunks, session_id="preproc_fail")
        assert res.has_errors
        assert res.segments == []
        err_events = [e for e in res.events if e.event_type == TranscriptEventType.ERROR]
        assert any(e.error.code == "PREPROCESSING_FAILED" for e in err_events)

    def test_no_misleading_successful_segments_on_failure(self):
        """When an error occurs, no final segments are reported as successful."""
        adapter = FakeTranscriber(fail_at_chunk_index=0)
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = _make_w1_chunks(3)
        res = orch.transcribe(chunks, session_id="no_mislead")
        assert res.has_errors
        assert len(res.segments) == 0
        assert res.full_text == ""


