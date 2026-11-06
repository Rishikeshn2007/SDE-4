"""
Unit tests for Day 3-4: BaseTranscriberAdapter and Deterministic FakeTranscriber.
"""

import pytest
from academia_audio import AudioChunk, AudioFormat
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.schemas.transcript import TranscriptEventType

FMT = AudioFormat(16000, 1)


class TestFakeTranscriber:
    def test_determinism_identical_runs_produce_identical_events(self):
        """Guarantee: same input chunks -> 100% identical transcript events."""
        chunks = [
            AudioChunk(sequence_id=0, timestamp_s=0.0, format=FMT, data=b"\x01\x00" * 4000),
            AudioChunk(sequence_id=1, timestamp_s=0.25, format=FMT, data=b"\x02\x00" * 4000),
            AudioChunk(sequence_id=2, timestamp_s=0.5, format=FMT, data=b"\x03\x00" * 4000),
        ]

        transcriber_a = FakeTranscriber(canned_transcript="Why is this code failing")
        transcriber_b = FakeTranscriber(canned_transcript="Why is this code failing")

        events_a = list(transcriber_a.transcribe_stream(chunks, session_id="sess_det_123"))
        events_b = list(transcriber_b.transcribe_stream(chunks, session_id="sess_det_123"))

        assert len(events_a) == len(events_b)
        assert len(events_a) > 0

        for ea, eb in zip(events_a, events_b):
            assert ea.event_id == eb.event_id
            assert ea.event_type == eb.event_type
            assert ea.timestamp == eb.timestamp
            if ea.segment:
                assert ea.segment.text == eb.segment.text
                assert ea.segment.is_final == eb.segment.is_final
                assert ea.segment.start_time == eb.segment.start_time
                assert ea.segment.end_time == eb.segment.end_time
                assert ea.segment.confidence == eb.segment.confidence

    def test_lifecycle_events_progression(self):
        """Verifies START -> INTERIM -> FINAL -> COMPLETE lifecycle."""
        transcriber = FakeTranscriber(canned_transcript="Explain this error")
        
        # 1. Start
        start_events = transcriber.start_session("sess_001")
        assert len(start_events) == 1
        assert start_events[0].event_type == TranscriptEventType.START

        # 2. Chunk 1 (interim)
        chunk1 = AudioChunk(sequence_id=0, timestamp_s=0.0, format=FMT, data=b"\x01\x00" * 8000)
        c1_events = transcriber.process_chunk(chunk1)
        assert len(c1_events) == 1
        assert c1_events[0].event_type == TranscriptEventType.INTERIM
        assert not c1_events[0].segment.is_final

        # 3. Chunk 2 (last chunk -> emits FINAL + COMPLETE)
        chunk2 = AudioChunk(sequence_id=1, timestamp_s=1.0, format=FMT, data=b"\x02\x00" * 8000)
        c2_events = transcriber.process_chunk(chunk2, is_last=True)
        assert len(c2_events) == 2
        assert c2_events[0].event_type == TranscriptEventType.FINAL
        assert c2_events[0].segment.is_final is True
        assert c2_events[0].segment.text == "Explain this error"
        assert c2_events[1].event_type == TranscriptEventType.COMPLETE

    def test_finish_session_flushes_pending_transcript(self):
        """When audio stream ends without is_last flag, finish_session flushes final event."""
        transcriber = FakeTranscriber(canned_transcript="Run unit tests")
        transcriber.start_session("sess_002")
        
        chunk = AudioChunk(sequence_id=0, timestamp_s=0.0, format=FMT, data=b"\x01\x00" * 6400)
        interim = transcriber.process_chunk(chunk)
        assert interim[0].event_type == TranscriptEventType.INTERIM

        flush_events = transcriber.finish_session()
        assert len(flush_events) == 2
        assert flush_events[0].event_type == TranscriptEventType.FINAL
        assert flush_events[0].segment.is_final is True
        assert flush_events[1].event_type == TranscriptEventType.COMPLETE
        assert not transcriber.is_active

    def test_raw_bytes_input_support(self):
        """Transcriber accepts raw bytes in addition to AudioChunk."""
        transcriber = FakeTranscriber()
        transcriber.start_session("sess_bytes")
        
        raw_pcm = b"\x00\x01" * 16000  # 1 second of 16kHz 16-bit mono
        events = transcriber.process_chunk(raw_pcm)
        assert len(events) == 1
        assert events[0].event_type == TranscriptEventType.INTERIM
        assert events[0].segment.end_time == 1.0

    def test_simulated_error_injection(self):
        """Transcriber can inject an ERROR event on a designated chunk index."""
        transcriber = FakeTranscriber(fail_at_chunk_index=1, error_code="MIC_DISCONNECTED")
        transcriber.start_session("sess_err")

        chunk0 = AudioChunk(sequence_id=0, timestamp_s=0.0, format=FMT, data=b"\x01\x00" * 4000)
        evts0 = transcriber.process_chunk(chunk0)
        assert evts0[0].event_type == TranscriptEventType.INTERIM

        chunk1 = AudioChunk(sequence_id=1, timestamp_s=0.25, format=FMT, data=b"\x02\x00" * 4000)
        evts1 = transcriber.process_chunk(chunk1)
        assert len(evts1) == 1
        assert evts1[0].event_type == TranscriptEventType.ERROR
        assert evts1[0].error.code == "MIC_DISCONNECTED"
        assert not transcriber.is_active

    def test_process_chunk_without_start_raises_runtime_error(self):
        transcriber = FakeTranscriber()
        with pytest.raises(RuntimeError):
            transcriber.process_chunk(b"some_audio")

    def test_invalid_session_id_raises_value_error(self):
        transcriber = FakeTranscriber()
        with pytest.raises(ValueError):
            transcriber.start_session("   ")

    def test_w1_mock_microphone_chunk_compatibility(self):
        """Transcriber seamlessly processes AudioChunk objects from academia_audio (W1)."""
        from academia_audio import MockMicrophone

        mic = MockMicrophone(duration_s=0.1, chunk_ms=20)
        chunks = list(mic.stream())
        assert len(chunks) == 5

        transcriber = FakeTranscriber(canned_transcript="Testing academia audio integration")
        events = list(transcriber.transcribe_stream(chunks, session_id="sess_w1"))
        assert len(events) >= 2
        assert events[0].event_type == TranscriptEventType.START
        assert events[-1].event_type == TranscriptEventType.COMPLETE

    def test_reject_invalid_chunk_type(self):
        transcriber = FakeTranscriber()
        transcriber.start_session("sess_type_err")
        with pytest.raises(TypeError):
            transcriber.process_chunk(12345)  # type: ignore


# ---------------------------------------------------------------------------
# RealSpeechTranscriber Unit & Orchestrator Integration Tests
# ---------------------------------------------------------------------------

import sys
from unittest.mock import MagicMock


@pytest.fixture
def mock_sr(monkeypatch):
    """Inject a fake speech_recognition module so RealSpeechTranscriber can be
    instantiated in environments where the real package is not installed."""
    fake_sr = MagicMock()
    # Recognizer() returns a MagicMock; individual methods can be patched per-test
    fake_sr.Recognizer.return_value = MagicMock()
    fake_sr.AudioData = MagicMock()
    # Make SR exception types subclass Exception so except-clauses work
    fake_sr.UnknownValueError = type("UnknownValueError", (Exception,), {})
    fake_sr.RequestError = type("RequestError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "speech_recognition", fake_sr)
    return fake_sr


class TestRealSpeechTranscriberIntegration:
    """Verifies RealSpeechTranscriber contract and integration with TranscriptionOrchestrator."""

    def test_real_transcriber_orchestrator_integration(self, mock_sr, monkeypatch):
        """RealSpeechTranscriber integrates with TranscriptionOrchestrator seamlessly."""
        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber
        from sde4_stt.orchestrator import TranscriptionOrchestrator

        real_adapter = RealSpeechTranscriber(language="en-US", sample_rate=16000)

        # Mock the network recognize_google call to return deterministic output offline
        monkeypatch.setattr(
            real_adapter._recognizer,
            "recognize_google",
            lambda audio_data, language="en-US": "integration test speech recognized successfully",
        )

        orch = TranscriptionOrchestrator(adapter=real_adapter)
        chunks = [
            AudioChunk(sequence_id=0, timestamp_s=0.0, format=FMT, data=b"\x00\x00" * 1600),
            AudioChunk(sequence_id=1, timestamp_s=0.1, format=FMT, data=b"\x00\x00" * 1600),
        ]

        result = orch.transcribe(chunks, session_id="real_orch_session")
        assert not result.has_errors
        assert result.full_text == "integration test speech recognized successfully"
        assert len(result.segments) == 1
        assert result.segments[0].is_final is True
        assert result.chunks_processed == 2

    def test_real_transcriber_buffered_batch_contract(self, mock_sr, monkeypatch):
        """RealSpeechTranscriber buffers chunks and emits no fake interims until finish_session."""
        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber

        adapter = RealSpeechTranscriber(language="en-US", sample_rate=16000)
        start_events = adapter.start_session("sess_buffered")
        assert len(start_events) == 1
        assert start_events[0].event_type == TranscriptEventType.START

        # process_chunk returns empty list (no fabricated interims)
        chunk = AudioChunk(sequence_id=0, timestamp_s=0.0, format=FMT, data=b"\x01\x00" * 3200)
        chunk_events = adapter.process_chunk(chunk)
        assert chunk_events == []
        assert len(adapter._audio_buffer) == 6400

        # Mock recognize_google for finish_session
        monkeypatch.setattr(
            adapter._recognizer,
            "recognize_google",
            lambda audio_data, language="en-US": "buffered audio transcribed",
        )
        finish_events = adapter.finish_session()
        assert len(finish_events) == 2
        assert finish_events[0].event_type == TranscriptEventType.FINAL
        assert finish_events[0].segment.text == "buffered audio transcribed"
        assert finish_events[1].event_type == TranscriptEventType.COMPLETE
        assert not adapter.is_active

    def test_real_transcriber_handles_empty_buffer(self, mock_sr):
        """RealSpeechTranscriber handles zero audio chunks gracefully without calling network."""
        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber

        adapter = RealSpeechTranscriber(language="en-US", sample_rate=16000)
        adapter.start_session("sess_empty")
        finish_events = adapter.finish_session()
        assert len(finish_events) == 1
        assert finish_events[0].event_type == TranscriptEventType.COMPLETE
        assert not adapter.is_active

    def test_raises_import_error_without_speech_recognition(self, monkeypatch):
        """Constructing RealSpeechTranscriber without SpeechRecognition raises a clear ImportError."""
        # Setting the entry to None in sys.modules causes `import speech_recognition`
        # to raise ImportError immediately (Python's import machinery behaviour).
        monkeypatch.setitem(sys.modules, "speech_recognition", None)

        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber

        with pytest.raises(ImportError, match="SpeechRecognition is required"):
            RealSpeechTranscriber()

    # -----------------------------------------------------------------------
    # Documentation-accuracy regression tests (W1 review fix)
    # -----------------------------------------------------------------------

    def test_process_chunk_never_emits_interim_events(self, mock_sr):
        """process_chunk() must always return [] — no fabricated INTERIM events."""
        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber

        adapter = RealSpeechTranscriber()
        adapter.start_session("sess_no_interim")

        for i in range(3):
            chunk = AudioChunk(
                sequence_id=i,
                timestamp_s=i * 0.1,
                format=FMT,
                data=b"\x01\x00" * 800,
            )
            result = adapter.process_chunk(chunk)
            assert result == [], (
                f"process_chunk() emitted events on chunk {i}; "
                "RealSpeechTranscriber must not fabricate INTERIM events."
            )

    def test_finish_session_is_sole_recognition_trigger(self, mock_sr, monkeypatch):
        """Audio is transcribed only when finish_session() is called, not during buffering."""
        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber

        adapter = RealSpeechTranscriber()
        adapter.start_session("sess_trigger")

        recognize_call_count = 0

        def counting_recognize(audio_data, language="en-US"):
            nonlocal recognize_call_count
            recognize_call_count += 1
            return "trigger test"

        monkeypatch.setattr(adapter._recognizer, "recognize_google", counting_recognize)

        # Feed two chunks — no recognition should happen yet
        for i in range(2):
            adapter.process_chunk(
                AudioChunk(sequence_id=i, timestamp_s=i * 0.1, format=FMT, data=b"\x00\x01" * 800)
            )
        assert recognize_call_count == 0, (
            "recognize_google() was called during process_chunk(); "
            "recognition must be deferred until finish_session()."
        )

        # Recognition fires exactly once on finish_session
        events = adapter.finish_session()
        assert recognize_call_count == 1
        event_types = [e.event_type for e in events]
        assert TranscriptEventType.FINAL in event_types
        assert TranscriptEventType.COMPLETE in event_types

    def test_word_timings_confidence_is_none(self, mock_sr, monkeypatch):
        """Word-level confidence must be None (not a fabricated score)."""
        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber

        adapter = RealSpeechTranscriber()
        adapter.start_session("sess_word_conf")
        adapter.process_chunk(
            AudioChunk(sequence_id=0, timestamp_s=0.0, format=FMT, data=b"\x00\x00" * 3200)
        )
        monkeypatch.setattr(
            adapter._recognizer,
            "recognize_google",
            lambda audio_data, language="en-US": "hello world foo",
        )
        events = adapter.finish_session()
        final_event = next(e for e in events if e.event_type == TranscriptEventType.FINAL)
        assert final_event.segment.words is not None
        for wt in final_event.segment.words:
            assert wt.confidence is None, (
                f"Word '{wt.word}' has confidence={wt.confidence!r}; "
                "recognize_google() does not supply word confidences — must be None."
            )

    def test_segment_confidence_is_schema_default_not_fabricated(self, mock_sr, monkeypatch):
        """Segment confidence must equal the schema default (1.0), not a hardcoded 0.95."""
        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber

        adapter = RealSpeechTranscriber()
        adapter.start_session("sess_seg_conf")
        adapter.process_chunk(
            AudioChunk(sequence_id=0, timestamp_s=0.0, format=FMT, data=b"\x00\x00" * 3200)
        )
        monkeypatch.setattr(
            adapter._recognizer,
            "recognize_google",
            lambda audio_data, language="en-US": "confidence check",
        )
        events = adapter.finish_session()
        final_event = next(e for e in events if e.event_type == TranscriptEventType.FINAL)
        # Must not be 0.95 (the former fabricated value).
        assert final_event.segment.confidence != 0.95, (
            "Segment confidence is 0.95 — this is a fabricated value not supplied "
            "by recognize_google(). Use the schema default (1.0) instead."
        )
        # Must equal the schema default (1.0).
        assert final_event.segment.confidence == 1.0

    def test_word_timings_are_estimated_equal_division(self, mock_sr, monkeypatch):
        """Word timestamps are estimated by equal division, not provider-supplied alignments."""
        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber

        # 3200 bytes @ 16 kHz / 2-byte samples = 0.1 s duration
        adapter = RealSpeechTranscriber(sample_rate=16000, sample_width=2)
        adapter.start_session("sess_word_ts")
        adapter.process_chunk(
            AudioChunk(sequence_id=0, timestamp_s=0.0, format=FMT, data=b"\x00\x00" * 3200)
        )
        monkeypatch.setattr(
            adapter._recognizer,
            "recognize_google",
            lambda audio_data, language="en-US": "one two",
        )
        events = adapter.finish_session()
        final_event = next(e for e in events if e.event_type == TranscriptEventType.FINAL)
        words = final_event.segment.words
        assert words is not None and len(words) == 2

        # Verify equal-division geometry: each word gets half the total duration
        total_duration = final_event.segment.end_time
        expected_half = round(total_duration / 2, 3)
        assert words[0].start_time == 0.0
        assert abs(words[0].end_time - expected_half) < 1e-6
        assert abs(words[1].start_time - expected_half) < 1e-6
        assert abs(words[1].end_time - total_duration) < 1e-6

    def test_is_last_flag_has_no_effect(self, mock_sr):
        """is_last=True on process_chunk() must not trigger recognition or return events."""
        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber

        adapter = RealSpeechTranscriber()
        adapter.start_session("sess_is_last")
        chunk = AudioChunk(sequence_id=0, timestamp_s=0.0, format=FMT, data=b"\x00\x00" * 800)
        result = adapter.process_chunk(chunk, is_last=True)
        assert result == [], (
            "process_chunk(is_last=True) returned events; "
            "is_last is ignored — explicit finish_session() is required."
        )
        # Session should still be active (finish_session not called)
        assert adapter.is_active

