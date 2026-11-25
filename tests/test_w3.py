"""
Week 3 Tests: Revisions, Finalization, Session Awareness, Cancellation,
Mock Fallback, and W1 Audio / W5 Backend Event-Stream Integration.
"""

from __future__ import annotations

import time
from typing import List, Optional, Union
import pytest

from academia_audio.mock_source import MockMicrophone
from academia_audio.schemas import AudioChunk, AudioFormat
from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.dedup import EventDeduplicator
from sde4_stt.event_bridge import EventBridgePublisher, make_no_op_publisher
from sde4_stt.fallback import FallbackAdapter
from sde4_stt.orchestrator import TranscriptionOrchestrator, TranscriptionResult
from sde4_stt.retry import NormalizedError
from sde4_stt.schemas.transcript import (
    TranscriptError,
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
    WordTiming,
)
from sde4_stt.session import CancellationToken, SessionContext, SessionManager


# ---------------------------------------------------------------------------
# Helpers & Mocks
# ---------------------------------------------------------------------------

def make_chunk(seq: int = 0, duration_ms: int = 250, is_last: bool = False) -> AudioChunk:
    """Helper to construct valid W1 AudioChunk objects."""
    n_samples = int(16000 * (duration_ms / 1000.0))
    raw_pcm = b"\x00\x00" * (n_samples * 2)
    fmt = AudioFormat(sample_rate=16000, channels=1)
    return AudioChunk(
        sequence_id=seq,
        timestamp_s=seq * (duration_ms / 1000.0),
        format=fmt,
        data=raw_pcm,
    )


class FailingAdapter(BaseTranscriberAdapter):
    """Adapter that fails with a specific error on start_session or process_chunk."""

    def __init__(self, exc_to_raise: Exception, fail_at: str = "start"):
        super().__init__(provider_name="failing-provider")
        self.exc_to_raise = exc_to_raise
        self.fail_at = fail_at

    def start_session(self, session_id: str, language: str = "en", sample_rate: int = 16000) -> List[TranscriptEvent]:
        self._session_id = session_id
        if self.fail_at == "start":
            raise self.exc_to_raise
        self._is_active = True
        return [
            TranscriptEvent(
                event_id=f"evt_{session_id}_start",
                session_id=session_id,
                event_type=TranscriptEventType.START,
                timestamp=time.time(),
            )
        ]

    def process_chunk(self, chunk: Union[AudioChunk, bytes], is_last: bool = False) -> List[TranscriptEvent]:
        if self.fail_at == "chunk":
            raise self.exc_to_raise
        return []

    def finish_session(self) -> List[TranscriptEvent]:
        self._is_active = False
        return [
            TranscriptEvent(
                event_id=f"evt_{self._session_id}_complete",
                session_id=self._session_id or "unknown",
                event_type=TranscriptEventType.COMPLETE,
                timestamp=time.time(),
            )
        ]


# ---------------------------------------------------------------------------
# D15–16: Revision, Finalization, and Session Awareness
# ---------------------------------------------------------------------------

class TestTranscriptRevisionAndFinalization:
    """Tests for interim, revision, finalization, and duplicate suppression."""

    def test_interim_transcription_emitted(self):
        adapter = FakeTranscriber(canned_transcript="hello world")
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = [make_chunk(0), make_chunk(1, is_last=True)]

        res = orch.transcribe(chunks, session_id="sess_rev_1")
        interims = [e for e in res.events if e.event_type == TranscriptEventType.INTERIM]
        assert len(interims) >= 1
        assert interims[0].segment is not None
        assert interims[0].segment.is_final is False

    def test_revised_transcription_emitted_and_supersedes_interim(self):
        dedup = EventDeduplicator()
        seg_interim = TranscriptSegment(
            segment_id="seg_0", sequence_number=0, text="hello wor",
            start_time=0.0, end_time=1.0, is_final=False, confidence=0.8
        )
        evt_interim = TranscriptEvent(
            event_id="evt_int_1", session_id="s1", event_type=TranscriptEventType.INTERIM,
            timestamp=100.0, segment=seg_interim
        )
        # 1. Process interim
        kept_int = dedup.process_event(evt_interim)
        assert kept_int is not None

        # 2. Process revised for same sequence
        seg_revised = TranscriptSegment(
            segment_id="seg_0", sequence_number=0, text="hello world",
            start_time=0.0, end_time=1.0, is_final=False, confidence=0.9
        )
        evt_revised = TranscriptEvent(
            event_id="evt_rev_1", session_id="s1", event_type=TranscriptEventType.REVISED,
            timestamp=101.0, segment=seg_revised
        )
        kept_rev = dedup.process_event(evt_revised)
        assert kept_rev is not None
        assert kept_rev.event_type == TranscriptEventType.REVISED
        assert kept_rev.segment.text == "hello world"

    def test_revised_cannot_overwrite_final(self):
        """Late REVISED arriving after FINAL must be suppressed."""
        dedup = EventDeduplicator()
        seg_final = TranscriptSegment(
            segment_id="seg_0", sequence_number=0, text="hello world final",
            start_time=0.0, end_time=1.0, is_final=True, confidence=0.95
        )
        evt_final = TranscriptEvent(
            event_id="evt_final_1", session_id="s1", event_type=TranscriptEventType.FINAL,
            timestamp=102.0, segment=seg_final
        )
        dedup.process_event(evt_final)

        # Now late REVISED arrives for sequence 0
        seg_late = TranscriptSegment(
            segment_id="seg_0", sequence_number=0, text="late revised text",
            start_time=0.0, end_time=1.0, is_final=False, confidence=0.7
        )
        evt_late = TranscriptEvent(
            event_id="evt_late_1", session_id="s1", event_type=TranscriptEventType.REVISED,
            timestamp=103.0, segment=seg_late
        )
        kept_late = dedup.process_event(evt_late)
        assert kept_late is None, "REVISED event must not overwrite an already-committed FINAL"
        assert dedup.num_interims_reconciled == 1

        # Final segment is intact
        finals = dedup.get_ordered_finals()
        assert len(finals) == 1
        assert finals[0].text == "hello world final"

    def test_duplicate_transcript_events_safely_handled(self):
        dedup = EventDeduplicator()
        seg = TranscriptSegment(
            segment_id="seg_0", sequence_number=0, text="hello",
            start_time=0.0, end_time=1.0, is_final=True, confidence=0.95
        )
        evt = TranscriptEvent(
            event_id="evt_dup_1", session_id="s1", event_type=TranscriptEventType.FINAL,
            timestamp=100.0, segment=seg
        )
        assert dedup.process_event(evt) is not None
        # Second time with same event_id
        assert dedup.process_event(evt) is None
        assert dedup.num_duplicates_suppressed == 1

    def test_final_event_emitted_with_is_final_true(self):
        adapter = FakeTranscriber(canned_transcript="complete test")
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = [make_chunk(0, is_last=True)]
        res = orch.transcribe(chunks, session_id="sess_final_1")

        finals = [e for e in res.events if e.event_type == TranscriptEventType.FINAL]
        assert len(finals) >= 1
        for f in finals:
            assert f.segment.is_final is True
            assert len(f.segment.text.strip()) > 0


class TestSessionAssociation:
    """Tests that session identity is strictly preserved across all events."""

    def test_session_id_preserved_across_all_events(self):
        session_id = "test_sess_ident_999"
        adapter = FakeTranscriber(canned_transcript="testing session identity")
        orch = TranscriptionOrchestrator(adapter=adapter)
        chunks = [make_chunk(0), make_chunk(1, is_last=True)]

        res = orch.transcribe(chunks, session_id=session_id)
        assert res.session_id == session_id
        assert len(res.events) > 0
        for event in res.events:
            assert event.session_id == session_id

    def test_multiple_sessions_no_cross_contamination(self):
        orch = TranscriptionOrchestrator(adapter=FakeTranscriber(canned_transcript="speech A"))
        res_a = orch.transcribe([make_chunk(0, is_last=True)], session_id="sess_A")

        orch_b = TranscriptionOrchestrator(adapter=FakeTranscriber(canned_transcript="speech B"))
        res_b = orch_b.transcribe([make_chunk(0, is_last=True)], session_id="sess_B")

        for ea in res_a.events:
            assert ea.session_id == "sess_A"
            assert "sess_B" not in ea.event_id
        for eb in res_b.events:
            assert eb.session_id == "sess_B"
            assert "sess_A" not in eb.event_id

    def test_session_manager_crud_and_cancellation(self):
        mgr = SessionManager()
        ctx = mgr.create_session("sess_mgr_1", confidence_threshold=0.8)
        assert ctx.session_id == "sess_mgr_1"
        assert ctx.confidence_threshold == 0.8
        assert ctx.is_cancelled is False

        # Duplicate create raises ValueError
        with pytest.raises(ValueError):
            mgr.create_session("sess_mgr_1")

        # Cancel
        assert mgr.cancel_session("sess_mgr_1") is True
        assert ctx.is_cancelled is True

        # Cancel nonexistent
        assert mgr.cancel_session("nonexistent") is False

        # Remove
        mgr.remove_session("sess_mgr_1")
        assert mgr.get_session("sess_mgr_1") is None


class TestConfidenceThresholds:
    """Tests for configurable confidence thresholds."""

    def test_low_confidence_segment_triggers_error_event(self):
        # FakeTranscriber with confidence 0.5, threshold 0.8
        adapter = FakeTranscriber(canned_transcript="low conf text", fixed_confidence=0.5)
        orch = TranscriptionOrchestrator(adapter=adapter, confidence_threshold=0.8)
        chunks = [make_chunk(0, is_last=True)]

        res = orch.transcribe(chunks, session_id="sess_conf_low")
        low_conf_errors = [
            e for e in res.events
            if e.event_type == TranscriptEventType.ERROR and e.error and e.error.code == "LOW_CONFIDENCE"
        ]
        assert len(low_conf_errors) >= 1
        assert low_conf_errors[0].error.recoverable is True
        # Final segment is still present in results
        assert len(res.segments) >= 1

    def test_high_confidence_segment_normal_processing(self):
        # FakeTranscriber with confidence 0.95, threshold 0.8
        adapter = FakeTranscriber(canned_transcript="high conf text", fixed_confidence=0.95)
        orch = TranscriptionOrchestrator(adapter=adapter, confidence_threshold=0.8)
        chunks = [make_chunk(0, is_last=True)]

        res = orch.transcribe(chunks, session_id="sess_conf_high")
        low_conf_errors = [
            e for e in res.events
            if e.event_type == TranscriptEventType.ERROR and e.error and e.error.code == "LOW_CONFIDENCE"
        ]
        assert len(low_conf_errors) == 0
        assert len(res.segments) >= 1

    def test_threshold_at_exact_boundary(self):
        adapter = FakeTranscriber(canned_transcript="exact conf text", fixed_confidence=0.80)
        orch = TranscriptionOrchestrator(adapter=adapter, confidence_threshold=0.80)
        chunks = [make_chunk(0, is_last=True)]

        res = orch.transcribe(chunks, session_id="sess_conf_boundary")
        low_conf_errors = [
            e for e in res.events
            if e.event_type == TranscriptEventType.ERROR and e.error and e.error.code == "LOW_CONFIDENCE"
        ]
        assert len(low_conf_errors) == 0


# ---------------------------------------------------------------------------
# D17–18: Cancellation and Mock Provider Fallback
# ---------------------------------------------------------------------------

class TestCancellation:
    """Tests for cancellation of ongoing transcription sessions."""

    def test_cancellation_stops_inflight_processing(self):
        token = CancellationToken()
        adapter = FakeTranscriber(canned_transcript="first second third fourth")
        orch = TranscriptionOrchestrator(adapter=adapter, cancellation_token=token)

        # Cancel immediately
        token.cancel()
        chunks = [make_chunk(0), make_chunk(1), make_chunk(2, is_last=True)]
        res = orch.transcribe(chunks, session_id="sess_cancel_1")

        # Must have cancelled event and no final segments
        cancel_events = [e for e in res.events if e.event_type == TranscriptEventType.CANCELLED]
        assert len(cancel_events) == 1
        assert len(res.segments) == 0
        assert res.chunks_processed == 0

    def test_cancellation_not_treated_as_provider_failure(self):
        token = CancellationToken()
        token.cancel()
        orch = TranscriptionOrchestrator(adapter=FakeTranscriber(), cancellation_token=token)
        res = orch.transcribe([make_chunk(0)], session_id="sess_cancel_clean")

        # CANCELLED event emitted, has_errors should be False
        assert res.has_errors is False
        assert any(e.event_type == TranscriptEventType.CANCELLED for e in res.events)

    def test_cancellation_does_not_affect_other_sessions(self):
        token_a = CancellationToken()
        token_b = CancellationToken()
        token_a.cancel()  # only cancel A

        orch_a = TranscriptionOrchestrator(adapter=FakeTranscriber(), cancellation_token=token_a)
        orch_b = TranscriptionOrchestrator(adapter=FakeTranscriber(canned_transcript="session b alive"), cancellation_token=token_b)

        res_a = orch_a.transcribe([make_chunk(0, is_last=True)], session_id="sess_A")
        res_b = orch_b.transcribe([make_chunk(0, is_last=True)], session_id="sess_B")

        assert any(e.event_type == TranscriptEventType.CANCELLED for e in res_a.events)
        assert not any(e.event_type == TranscriptEventType.CANCELLED for e in res_b.events)
        assert len(res_b.segments) >= 1


class TestMockProviderFallback:
    """Tests for automatic fallback to mock provider on recoverable errors."""

    def test_network_failure_triggers_mock_fallback(self):
        primary = FailingAdapter(exc_to_raise=ConnectionError("DNS failure"), fail_at="start")
        fallback_target = FakeTranscriber(canned_transcript="recovered via mock")
        adapter = FallbackAdapter(primary=primary, fallback=fallback_target)

        events = adapter.start_session("sess_fall_net")
        assert adapter.using_fallback is True
        # Check that fallback notification was emitted
        assert any(
            e.event_type == TranscriptEventType.ERROR and e.error.code == "FALLBACK_ACTIVATED"
            for e in events
        )

        # Further chunk processing succeeds via fallback
        chunk_evts = adapter.process_chunk(make_chunk(0, is_last=True), is_last=True)
        assert any(e.event_type == TranscriptEventType.FINAL for e in chunk_evts)

    def test_quota_failure_triggers_mock_fallback(self):
        primary = FailingAdapter(exc_to_raise=PermissionError("Monthly quota exceeded"), fail_at="start")
        fallback_target = FakeTranscriber(canned_transcript="quota fallback text")
        adapter = FallbackAdapter(primary=primary, fallback=fallback_target)

        events = adapter.start_session("sess_fall_quota")
        assert adapter.using_fallback is True
        assert any(
            e.event_type == TranscriptEventType.ERROR and e.error.code == "FALLBACK_ACTIVATED"
            for e in events
        )

    def test_fallback_preserves_session_id(self):
        session_id = "sess_id_preservation_test"
        primary = FailingAdapter(exc_to_raise=ConnectionError("net drop"), fail_at="start")
        fallback_target = FakeTranscriber(canned_transcript="preserving session")
        adapter = FallbackAdapter(primary=primary, fallback=fallback_target)

        events = adapter.start_session(session_id)
        for e in events:
            assert e.session_id == session_id

        chunk_events = adapter.process_chunk(make_chunk(0, is_last=True), is_last=True)
        for e in chunk_events:
            assert e.session_id == session_id

    def test_fallback_provider_itself_fails_cleanly(self):
        """If both primary and fallback fail, emit error and avoid infinite loop."""
        primary = FailingAdapter(exc_to_raise=ConnectionError("primary down"), fail_at="start")
        bad_fallback = FailingAdapter(exc_to_raise=RuntimeError("mock also crashed"), fail_at="start")
        adapter = FallbackAdapter(primary=primary, fallback=bad_fallback)

        events = adapter.start_session("sess_double_fail")
        assert adapter.using_fallback is True
        # Must return error events rather than crashing with unhandled exception
        assert any(e.event_type == TranscriptEventType.ERROR for e in events)


# ---------------------------------------------------------------------------
# D19–20: W1 Audio Events and W5 Backend Event-Stream Integration
# ---------------------------------------------------------------------------

class TestW1AudioIntegration:
    """Tests verifying consumption of W1 audio streams and chunks."""

    def test_w1_mock_microphone_stream(self):
        """Verify real W1 MockMicrophone chunks flow into orchestrator cleanly."""
        mic = MockMicrophone(duration_s=0.5, chunk_ms=100)
        chunks = list(mic.stream())

        orch = TranscriptionOrchestrator(adapter=FakeTranscriber())
        res = orch.transcribe(chunks, session_id="sess_w1_mic")
        assert res.chunks_processed == len(chunks)
        assert len(res.segments) >= 1

    def test_out_of_order_chunks_ordered_correctly(self):
        c0 = make_chunk(seq=0)
        c1 = make_chunk(seq=1)
        c2 = make_chunk(seq=2, is_last=True)

        dedup = EventDeduplicator()
        # Create final events out of order: 2, 0, 1
        evts = [
            TranscriptEvent(
                event_id="e2", session_id="s1", event_type=TranscriptEventType.FINAL,
                timestamp=102.0, segment=TranscriptSegment(segment_id="s2", sequence_number=2, text="two", start_time=2.0, end_time=3.0, is_final=True)
            ),
            TranscriptEvent(
                event_id="e0", session_id="s1", event_type=TranscriptEventType.FINAL,
                timestamp=100.0, segment=TranscriptSegment(segment_id="s0", sequence_number=0, text="zero", start_time=0.0, end_time=1.0, is_final=True)
            ),
            TranscriptEvent(
                event_id="e1", session_id="s1", event_type=TranscriptEventType.FINAL,
                timestamp=101.0, segment=TranscriptSegment(segment_id="s1", sequence_number=1, text="one", start_time=1.0, end_time=2.0, is_final=True)
            ),
        ]
        dedup.process_events(evts)
        finals = dedup.get_ordered_finals()
        seqs = [s.sequence_number for s in finals]
        assert seqs == [0, 1, 2]

    def test_missing_chunks_handled_gracefully(self):
        """Orchestrator should process available chunks even if a sequence is missing."""
        c0 = make_chunk(seq=0)
        c2 = make_chunk(seq=2, is_last=True)  # seq 1 missing

        orch = TranscriptionOrchestrator(adapter=FakeTranscriber())
        res = orch.transcribe([c0, c2], session_id="sess_gap")
        assert res.chunks_processed == 2
        assert not res.has_errors


class TestW5BackendIntegration:
    """Tests for publishing events to the W5 backend event stream."""

    def test_w5_event_bridge_publishes_all_lifecycle_events(self):
        published: List[dict] = []

        def mock_publish(session_id: str, event_type: str, data: dict) -> None:
            published.append({"session_id": session_id, "event_type": event_type, "data": data})

        publisher = EventBridgePublisher(publish_fn=mock_publish)
        adapter = FakeTranscriber(canned_transcript="testing backend event stream bridge")
        orch = TranscriptionOrchestrator(adapter=adapter, event_publisher=publisher)

        chunks = [make_chunk(0), make_chunk(1, is_last=True)]
        res = orch.transcribe(chunks, session_id="sess_w5_bridge")

        assert publisher.publish_count > 0
        assert len(published) == publisher.publish_count

        event_types = [p["event_type"] for p in published]
        assert "START" in event_types
        assert "FINAL" in event_types
        assert "COMPLETE" in event_types

        # Verify all published session_ids match
        for item in published:
            assert item["session_id"] == "sess_w5_bridge"
            assert isinstance(item["data"], dict)

    def test_w5_event_bridge_exception_isolation(self):
        """Exceptions in backend publisher must never crash the STT pipeline."""
        def broken_publish(session_id: str, event_type: str, data: dict) -> None:
            raise ConnectionResetError("Backend connection reset")

        publisher = EventBridgePublisher(publish_fn=broken_publish)
        orch = TranscriptionOrchestrator(adapter=FakeTranscriber(), event_publisher=publisher)

        # Should complete successfully without raising ConnectionResetError
        res = orch.transcribe([make_chunk(0, is_last=True)], session_id="sess_iso")
        assert res.chunks_processed == 1
        assert len(publisher.publish_errors) > 0


# ---------------------------------------------------------------------------
# D21: End-to-End Workflow Verification
# ---------------------------------------------------------------------------

class TestEndToEndMockPipeline:
    """Complete end-to-end integration test in mock mode."""

    def test_full_pipeline_mock_mode_no_credentials(self):
        """
        1. W1 Audio chunks generated.
        2. Session managed via SessionContext.
        3. FallbackAdapter with primary + FakeTranscriber.
        4. EventBridgePublisher collects backend events.
        5. Ordered finals and metadata verified.
        """
        # Session setup
        session_id = "e2e_mock_session_final"
        token = CancellationToken()
        ctx = SessionContext(session_id=session_id, confidence_threshold=0.6, cancellation_token=token)

        # W1 Audio input
        mic = MockMicrophone(duration_s=0.4, chunk_ms=100)
        chunks = list(mic.stream())

        # STT provider with Fallback
        primary = FailingAdapter(exc_to_raise=ConnectionError("offline mode"), fail_at="start")
        fallback_target = FakeTranscriber(canned_transcript="academia voice bot offline test complete")
        fallback_adapter = FallbackAdapter(primary=primary, fallback=fallback_target)

        # W5 Backend publisher
        received_events = []
        publisher = EventBridgePublisher(
            publish_fn=lambda sid, etype, data: received_events.append((sid, etype, data))
        )

        # Orchestrator
        orch = TranscriptionOrchestrator(
            adapter=fallback_adapter,
            cancellation_token=ctx.cancellation_token,
            confidence_threshold=ctx.confidence_threshold,
            event_publisher=publisher,
        )

        # Execute
        result = orch.transcribe(chunks, session_id=ctx.session_id)

        # Verifications
        assert result.session_id == session_id
        assert result.chunks_processed == 4
        assert len(result.segments) > 0
        assert "academia voice bot" in result.full_text
        assert len(received_events) > 0

        # All events delivered with correct session ID
        for sid, etype, data in received_events:
            assert sid == session_id
            assert "event_id" in data
            assert "event_type" in data
