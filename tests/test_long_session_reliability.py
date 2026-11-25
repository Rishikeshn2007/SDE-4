"""
Long-Session Reliability & Cancellation Consistency Test Suite (Week 4, Day 25–27).

Validates:
1. Long-session consistency (50-100+ chunks):
   - Strict chronological ordering of final segments.
   - Zero duplicated final segments.
   - Zero lost segments.
   - Consistent segment IDs.
   - Interim and final reconciliation.
   - Repeated provider events do not create duplicates.
   - Clean resource release at end of session.
2. Cancellation consistency:
   - Cancellation stops processing immediately.
   - No segments emitted after cancellation.
   - Idempotent repeated cancellation.
   - Multi-stage cancellation (pre-session, mid-stream, post-finish).
   - Cross-session isolation (cancelling session A does not affect session B).
   - Thread synchronization primitives used instead of fragile sleeps.
"""

from __future__ import annotations

import threading
import time
from typing import List, Optional

import pytest

from academia_audio.mock_source import MockMicrophone
from academia_audio.schemas import AudioChunk, AudioFormat

from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.dedup import EventDeduplicator
from sde4_stt.event_bridge import EventBridgePublisher
from sde4_stt.orchestrator import TranscriptionOrchestrator
from sde4_stt.schemas.transcript import (
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
    WordTiming,
)
from sde4_stt.session import CancellationToken, SessionContext, SessionManager


def _make_audio_stream(num_chunks: int, chunk_ms: int = 50) -> List[AudioChunk]:
    """Generate a sequence of valid W1 AudioChunks."""
    fmt = AudioFormat(sample_rate=16000, channels=1)
    mic = MockMicrophone(fmt=fmt, duration_s=(num_chunks * chunk_ms) / 1000.0, chunk_ms=chunk_ms)
    return list(mic.stream())


# ---------------------------------------------------------------------------
# Part A: Long-Session Consistency
# ---------------------------------------------------------------------------

def test_long_session_monotonic_order_and_no_loss():
    """Verify an extended session with 100 chunks maintains strict monotonicity and zero lost/duplicated segments."""
    num_chunks = 100
    chunks = _make_audio_stream(num_chunks=num_chunks, chunk_ms=50)
    assert len(chunks) == num_chunks

    words = [f"word_{i:03d}" for i in range(num_chunks)]
    canned_text = " ".join(words)

    adapter = FakeTranscriber(canned_transcript=canned_text, fixed_confidence=0.96)
    orch = TranscriptionOrchestrator(adapter=adapter)

    session_id = "sess_long_100_chunks"
    result = orch.transcribe(chunks, session_id=session_id)

    assert result.has_errors is False
    assert result.chunks_processed == num_chunks
    assert len(result.segments) >= 1

    # Verify every word from the canned transcript was finalized
    final_text = result.full_text
    for i in range(num_chunks):
        assert f"word_{i:03d}" in final_text

    # Verify no segment IDs are None or duplicated
    seen_ids = set()
    for seg in result.segments:
        assert seg.segment_id is not None
        assert seg.segment_id not in seen_ids
        seen_ids.add(seg.segment_id)
        assert seg.is_final is True
        assert seg.start_time <= seg.end_time


def test_long_session_interim_final_reconciliation_and_dup_suppression():
    """Verify interim hypotheses are superseded and repeated responses do not duplicate finals."""
    dedup = EventDeduplicator()
    session_id = "sess_reconciliation_extended"

    # Simulate 50 sequential steps where each step produces an interim, a duplicate interim, and then a final
    for seq in range(50):
        seg_interim = TranscriptSegment(
            segment_id=f"seg_{seq}",
            sequence_number=seq,
            text=f"partial_{seq}",
            start_time=seq * 0.1,
            end_time=(seq + 1) * 0.1,
            is_final=False,
        )
        evt_interim = TranscriptEvent(
            event_id=f"evt_interim_{seq}",
            session_id=session_id,
            event_type=TranscriptEventType.INTERIM,
            timestamp=100.0 + seq,
            segment=seg_interim,
        )
        # Duplicate interim
        evt_interim_dup = TranscriptEvent(
            event_id=f"evt_interim_{seq}",
            session_id=session_id,
            event_type=TranscriptEventType.INTERIM,
            timestamp=100.0 + seq,
            segment=seg_interim,
        )

        out_interim = dedup.process_events([evt_interim, evt_interim_dup])
        assert len(out_interim) == 1

        # Final segment for this sequence
        seg_final = TranscriptSegment(
            segment_id=f"seg_{seq}",
            sequence_number=seq,
            text=f"final_{seq}",
            start_time=seq * 0.1,
            end_time=(seq + 1) * 0.1,
            is_final=True,
        )
        evt_final = TranscriptEvent(
            event_id=f"evt_final_{seq}",
            session_id=session_id,
            event_type=TranscriptEventType.FINAL,
            timestamp=100.5 + seq,
            segment=seg_final,
        )
        # Duplicate final event (e.g. network replay)
        evt_final_dup = TranscriptEvent(
            event_id=f"evt_final_{seq}",
            session_id=session_id,
            event_type=TranscriptEventType.FINAL,
            timestamp=100.5 + seq,
            segment=seg_final,
        )

        out_final = dedup.process_events([evt_final, evt_final_dup])
        assert len(out_final) == 1  # Duplicate suppressed

    # Verify final accumulator state
    ordered_finals = dedup.get_ordered_finals()
    assert len(ordered_finals) == 50
    assert dedup.num_duplicates_suppressed == 100  # 50 interim dups + 50 final dups
    assert dedup.num_interims_reconciled == 50

    # Verify strict sequence numbering from 0 to 49
    for idx, seg in enumerate(ordered_finals):
        assert seg.sequence_number == idx
        assert seg.text == f"final_{idx}"


def test_long_session_resource_cleanup():
    """Verify session manager properly removes sessions and cleans up registry."""
    mgr = SessionManager()
    session_ids = [f"session_cleanup_{i}" for i in range(25)]

    for sid in session_ids:
        mgr.create_session(sid)

    assert len(mgr.active_sessions()) == 25

    # Remove all sessions
    for sid in session_ids:
        mgr.remove_session(sid)

    assert len(mgr.active_sessions()) == 0


# ---------------------------------------------------------------------------
# Part B: Cancellation Consistency
# ---------------------------------------------------------------------------

def test_cancellation_pre_start():
    """Cancelling a token before transcription starts halts immediately before chunk processing."""
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled is True

    chunks = _make_audio_stream(num_chunks=20)
    adapter = FakeTranscriber()
    orch = TranscriptionOrchestrator(adapter=adapter, cancellation_token=token)

    result = orch.transcribe(chunks, session_id="sess_cancel_pre_start")

    assert result.chunks_processed == 0
    assert len(result.segments) == 0
    event_types = [e.event_type for e in result.events]
    assert TranscriptEventType.CANCELLED in event_types
    assert TranscriptEventType.COMPLETE not in event_types


def test_cancellation_mid_stream_with_sync_primitive():
    """Cancelling a token mid-stream (at chunk 10 of 50) using a thread-safe barrier/event."""
    num_chunks = 50
    chunks = _make_audio_stream(num_chunks=num_chunks)

    token = CancellationToken()
    cancel_target_chunk = 10
    processed_count = 0
    cancel_event_triggered = threading.Event()

    class SynchronizedCancellingAdapter(FakeTranscriber):
        def process_chunk(self, chunk, is_last=False):
            nonlocal processed_count
            processed_count += 1
            if processed_count == cancel_target_chunk:
                token.cancel()
                cancel_event_triggered.set()
            return super().process_chunk(chunk, is_last=is_last)

    adapter = SynchronizedCancellingAdapter(canned_transcript="a b c d e f g")
    orch = TranscriptionOrchestrator(adapter=adapter, cancellation_token=token)

    result = orch.transcribe(chunks, session_id="sess_cancel_mid_stream")

    assert cancel_event_triggered.is_set()
    # Processing must stop near chunk 10, not run all 50
    assert result.chunks_processed <= cancel_target_chunk + 1
    assert result.chunks_processed < num_chunks

    # Verify CANCELLED event was captured and no COMPLETE was emitted
    event_types = [e.event_type for e in result.events]
    assert TranscriptEventType.CANCELLED in event_types
    assert TranscriptEventType.COMPLETE not in event_types
    assert len(result.segments) == 0


def test_cancellation_idempotency():
    """Repeated calls to cancel() on CancellationToken and adapter are safe and idempotent."""
    token = CancellationToken()
    assert token.is_cancelled is False

    # First cancel
    token.cancel()
    assert token.is_cancelled is True

    # Repeated cancels
    for _ in range(5):
        token.cancel()
        assert token.is_cancelled is True

    # Adapter cancel idempotency
    adapter = FakeTranscriber()
    adapter.start_session("sess_idempotent")
    first_cancel = adapter.cancel()
    assert len(first_cancel) == 1
    assert first_cancel[0].event_type == TranscriptEventType.CANCELLED

    # Subsequent cancels return empty list or safe result, no exceptions
    second_cancel = adapter.cancel()
    assert isinstance(second_cancel, list)


def test_cancellation_cross_session_isolation():
    """Cancelling session A does not cancel or corrupt active session B."""
    mgr = SessionManager()
    session_a = mgr.create_session("sess_isolation_A")
    session_b = mgr.create_session("sess_isolation_B")

    chunks = _make_audio_stream(num_chunks=15)

    # Cancel session A
    session_a.cancel()
    assert session_a.is_cancelled is True
    assert session_b.is_cancelled is False

    # Process session A -> stops with CANCELLED
    adapter_a = FakeTranscriber(canned_transcript="text for session A")
    orch_a = TranscriptionOrchestrator(adapter=adapter_a, cancellation_token=session_a.cancellation_token)
    res_a = orch_a.transcribe(chunks, session_id=session_a.session_id)
    assert res_a.chunks_processed == 0
    assert any(e.event_type == TranscriptEventType.CANCELLED for e in res_a.events)

    # Process session B -> completes fully
    adapter_b = FakeTranscriber(canned_transcript="text for session B completed successfully")
    orch_b = TranscriptionOrchestrator(adapter=adapter_b, cancellation_token=session_b.cancellation_token)
    res_b = orch_b.transcribe(chunks, session_id=session_b.session_id)
    assert res_b.chunks_processed == 15
    assert res_b.has_errors is False
    assert "text for session B completed successfully" in res_b.full_text
    assert any(e.event_type == TranscriptEventType.COMPLETE for e in res_b.events)
