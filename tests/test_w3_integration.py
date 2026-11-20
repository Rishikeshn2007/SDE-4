"""
Week 3 Day 21 End-to-End Integration Tests.

Validates the complete pipeline:
W1 Audio Chunks -> STT Orchestrator -> Interim / Revision / Final Events
-> W5 Backend Event Stream -> Reasoning & Intent Extraction -> Workflow Plan
-> Approval Gate -> Approved Execution -> Successful Completion.

All tests run 100% offline without external STT providers or internet access.
"""

from __future__ import annotations

import time
from typing import List, Optional, Union
import pytest

from academia_audio.schemas import AudioChunk, AudioFormat
from workflow.schemas import WorkflowPlan, WorkflowResult, WorkflowState, WorkflowStep

from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.dedup import EventDeduplicator
from sde4_stt.event_bridge import EventBridgePublisher
from sde4_stt.fallback import FallbackAdapter
from sde4_stt.orchestrator import TranscriptionOrchestrator, TranscriptionResult
from sde4_stt.retry import NormalizedError
from sde4_stt.schemas.transcript import (
    TranscriptError,
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
)
from sde4_stt.session import CancellationToken, SessionManager
from sde4_stt.workflow_bridge import VoiceWorkflowBridge


def _make_audio_chunk(
    seq: int = 0,
    duration_ms: int = 250,
    data: Optional[bytes] = None,
) -> AudioChunk:
    """Helper to build valid W1 AudioChunk objects."""
    fmt = AudioFormat(sample_rate=16000, channels=1)
    if data is None:
        n_samples = int(16000 * (duration_ms / 1000.0))
        data = b"\x10\x00" * n_samples  # 16-bit PCM frames
    return AudioChunk(
        sequence_id=seq,
        timestamp_s=seq * (duration_ms / 1000.0),
        format=fmt,
        data=data,
    )


# ---------------------------------------------------------------------------
# Test 1: Full audio-to-workflow execution
# ---------------------------------------------------------------------------

def test_end_to_end_audio_to_workflow_approval_gate():
    """Full pipeline: Audio -> STT -> Interim -> Revision -> Final -> W5 Stream
    -> Reasoning -> Workflow -> Approval Gate -> Succeeded.
    """
    session_id = "sess_day21_e2e"
    backend_events: List[tuple] = []

    publisher = EventBridgePublisher(
        publish_fn=lambda sid, etype, payload: backend_events.append((sid, etype, payload))
    )

    # 1. Provide W1 audio chunks
    chunks = [
        _make_audio_chunk(0, data=b"\x01\x00" * 2000),
        _make_audio_chunk(1, data=b"\x02\x00" * 2000),
        _make_audio_chunk(2, data=b"\x03\x00" * 2000),
    ]

    # Adapter that starts with "calculate sum", gets revised to "calculate sum 15 25", and finalizes
    adapter = FakeTranscriber(
        canned_transcript="calculate sum 15 25",
        revision_at_chunk_index=1,
        revised_words=["calculate", "sum", "15", "25"],
    )

    orchestrator = TranscriptionOrchestrator(
        adapter=adapter,
        event_publisher=publisher,
    )

    # 2. Run STT Transcription
    result = orchestrator.transcribe(chunks, session_id=session_id)

    assert result.session_id == session_id
    assert len(result.segments) > 0
    assert "calculate sum 15 25" in result.full_text

    # Verify W5 event stream captured STT events with matching session_id
    stt_event_types = [e[1].upper() for e in backend_events]
    assert "START" in stt_event_types
    assert "FINAL" in stt_event_types
    assert "COMPLETE" in stt_event_types
    for sid, _, _ in backend_events:
        assert sid == session_id

    # 3. Connect to VoiceWorkflowBridge (Reasoning + Workflow + Approval Gate)
    bridge = VoiceWorkflowBridge(event_publisher=publisher)
    plan = bridge.reason_and_plan(
        session_id=session_id,
        transcript_text=result.full_text,
        force_consequential=True,  # sensitive action requiring approval
    )

    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.tool_name == "mock_calculator"
    assert step.inputs == {"a": 15.0, "b": 25.0}
    assert step.consequential is True

    # 4. First execution attempt without approval -> pauses at Approval Gate
    res1 = bridge.execute(plan, session_id=session_id)
    assert res1.state == WorkflowState.AWAITING_APPROVAL
    assert res1.approval_request is not None
    assert res1.approval_request.step_id == step.step_id
    assert "workflow_awaiting_approval" in [e[1] for e in backend_events]

    # 5. User provides explicit approval -> resumes and succeeds
    approvals = {res1.approval_request.step_id: True}
    res2 = bridge.execute(plan, session_id=session_id, approvals=approvals)
    assert res2.state == WorkflowState.SUCCEEDED
    assert len(res2.step_results) == 1
    assert res2.step_results[0]["output"]["result"] == 40.0  # 15.0 + 25.0
    assert "workflow_succeeded" in [e[1] for e in backend_events]


# ---------------------------------------------------------------------------
# Test 2: Out-of-order chunks handled correctly
# ---------------------------------------------------------------------------

def test_out_of_order_chunks_handled_correctly():
    """Chunks arriving out of sequence are sorted chronologically by sequence_id."""
    session_id = "sess_out_of_order"
    c0 = _make_audio_chunk(seq=0, duration_ms=100)
    c1 = _make_audio_chunk(seq=1, duration_ms=100)
    c2 = _make_audio_chunk(seq=2, duration_ms=100)

    # Scrambled input order
    scrambled = [c2, c0, c1]

    processed_seqs = []

    class OrderTrackingAdapter(BaseTranscriberAdapter):
        def __init__(self):
            super().__init__("order-tracker")
        def start_session(self, session_id, language="en", sample_rate=16000):
            self._session_id = session_id
            return [TranscriptEvent(event_id=f"evt_{session_id}_start", session_id=session_id, event_type=TranscriptEventType.START, timestamp=time.time())]
        def process_chunk(self, chunk, is_last=False):
            processed_seqs.append(chunk.sequence_id)
            return []
        def finish_session(self):
            return [
                TranscriptEvent(
                    event_id=f"evt_{self._session_id}_final",
                    session_id=self._session_id,
                    event_type=TranscriptEventType.FINAL,
                    timestamp=time.time(),
                    segment=TranscriptSegment(segment_id="seg_order_1", sequence_number=0, text="ordered speech", start_time=0.0, end_time=0.3, is_final=True),
                )
            ]

    orch = TranscriptionOrchestrator(adapter=OrderTrackingAdapter())
    result = orch.transcribe(scrambled, session_id=session_id)

    assert result.has_errors is False
    assert processed_seqs == [0, 1, 2], f"Expected chronological ordering [0, 1, 2], got {processed_seqs}"
    assert len(result.segments) == 1
    assert result.segments[0].text == "ordered speech"


# ---------------------------------------------------------------------------
# Test 3: Missing chunks handled gracefully
# ---------------------------------------------------------------------------

def test_missing_chunks_handled_gracefully():
    """Dropped / missing chunks in stream do not stall or crash the orchestrator."""
    session_id = "sess_missing_chunks"
    c0 = _make_audio_chunk(seq=0, duration_ms=100)
    c2 = _make_audio_chunk(seq=2, duration_ms=100)  # chunk 1 is missing

    adapter = FakeTranscriber(canned_transcript="hello world")
    orch = TranscriptionOrchestrator(adapter=adapter)

    result = orch.transcribe([c0, c2], session_id=session_id)
    assert result.has_errors is False
    assert result.chunks_processed == 2
    assert "hello world" in result.full_text


# ---------------------------------------------------------------------------
# Test 4: In-flight cancellation and idempotency
# ---------------------------------------------------------------------------

def test_cancellation_in_flight_and_repeated():
    """Cancellation stops processing mid-flight, emits CANCELLED event,
    does not emit duplicate finals, and repeated cancel() is safe and idempotent.
    """
    session_id = "sess_cancellation"
    token = CancellationToken()

    chunks = [
        _make_audio_chunk(0, duration_ms=100),
        _make_audio_chunk(1, duration_ms=100),
        _make_audio_chunk(2, duration_ms=100),
    ]

    class EarlyCancellingAdapter(FakeTranscriber):
        def process_chunk(self, chunk, is_last=False):
            if chunk.sequence_id == 1:
                token.cancel()  # cancel mid-flight during chunk 1
            return super().process_chunk(chunk, is_last=is_last)

    adapter = EarlyCancellingAdapter(canned_transcript="never finished")
    orch = TranscriptionOrchestrator(adapter=adapter, cancellation_token=token)

    result = orch.transcribe(chunks, session_id=session_id)

    # Should have stopped before finishing all 3 chunks
    assert result.chunks_processed < 3
    event_types = [e.event_type for e in result.events]
    assert TranscriptEventType.CANCELLED in event_types
    assert TranscriptEventType.COMPLETE not in event_types

    # Repeated cancellation calls are idempotent
    token.cancel()
    assert token.is_cancelled is True
    repeated_events = adapter.cancel()
    assert isinstance(repeated_events, list)


# ---------------------------------------------------------------------------
# Test 5: Quota exhaustion automatic mock fallback
# ---------------------------------------------------------------------------

def test_quota_exhaustion_automatic_mock_fallback():
    """Primary provider throwing quota exhaustion activates mock fallback and completes."""
    session_id = "sess_quota_fallback"

    class QuotaFailingPrimary(BaseTranscriberAdapter):
        def __init__(self):
            super().__init__("cloud-stt-quota")
        def start_session(self, session_id, language="en", sample_rate=16000):
            return []
        def process_chunk(self, chunk, is_last=False):
            raise NormalizedError(
                code=NormalizedError.QUOTA_EXHAUSTED,
                message="Quota limit reached (429)",
                recoverable=True,
            )
        def finish_session(self):
            return []

    fallback = FakeTranscriber(canned_transcript="fallback query resolved")
    adapter = FallbackAdapter(primary=QuotaFailingPrimary(), fallback=fallback)
    orch = TranscriptionOrchestrator(adapter=adapter)

    chunks = [_make_audio_chunk(0), _make_audio_chunk(1)]
    result = orch.transcribe(chunks, session_id=session_id)

    assert adapter.using_fallback is True
    assert "fallback query resolved" in result.full_text
    # Fallback notification event was emitted
    error_codes = [e.error.code for e in result.events if e.error is not None]
    assert "FALLBACK_ACTIVATED" in error_codes


# ---------------------------------------------------------------------------
# Test 6: Network failure automatic mock fallback
# ---------------------------------------------------------------------------

def test_network_failure_automatic_mock_fallback():
    """Network connection failure during finish_session activates fallback cleanly."""
    session_id = "sess_network_fallback"

    class NetworkFailingPrimary(BaseTranscriberAdapter):
        def __init__(self):
            super().__init__("cloud-stt-network")
        def start_session(self, session_id, language="en", sample_rate=16000):
            return []
        def process_chunk(self, chunk, is_last=False):
            return []
        def finish_session(self):
            raise ConnectionError("TLS handshake timed out / connection reset by peer")

    fallback = FakeTranscriber(canned_transcript="offline fallback transcription")
    adapter = FallbackAdapter(primary=NetworkFailingPrimary(), fallback=fallback)
    orch = TranscriptionOrchestrator(adapter=adapter)

    chunks = [_make_audio_chunk(0), _make_audio_chunk(1)]
    result = orch.transcribe(chunks, session_id=session_id)

    assert adapter.using_fallback is True
    assert "offline fallback transcription" in result.full_text


# ---------------------------------------------------------------------------
# Test 7: Approval gate enforcement (rejection & approval)
# ---------------------------------------------------------------------------

def test_approval_gate_enforcement():
    """Consequential action pauses in AWAITING_APPROVAL; rejection stops execution;
    approval permits execution to SUCCEEDED.
    """
    bridge = VoiceWorkflowBridge()
    session_id = "sess_approval_gate"

    # Intent with consequential keyword "delete"
    plan = bridge.reason_and_plan(session_id, "delete all temporary logs", force_consequential=True)
    assert plan.steps[0].consequential is True
    step_id = plan.steps[0].step_id

    # 1. Without approval -> pauses
    res_pending = bridge.execute(plan, session_id=session_id)
    assert res_pending.state == WorkflowState.AWAITING_APPROVAL
    assert res_pending.approval_request is not None

    # 2. Explicit rejection -> remains not executed
    res_rejected = bridge.execute(plan, session_id=session_id, approvals={step_id: False})
    assert res_rejected.state == WorkflowState.AWAITING_APPROVAL

    # 3. Explicit approval -> succeeds
    res_approved = bridge.execute(plan, session_id=session_id, approvals={step_id: True})
    assert res_approved.state == WorkflowState.SUCCEEDED
    assert len(res_approved.step_results) == 1


# ---------------------------------------------------------------------------
# Test 8: Duplicate suppression and interim-final reconciliation
# ---------------------------------------------------------------------------

def test_duplicate_and_reconciliation_behavior():
    """Duplicate chunks do not create duplicate events; interims are reconciled by final."""
    session_id = "sess_dedup_reconcile"
    dedup = EventDeduplicator()

    seg_interim = TranscriptSegment(segment_id="s1", sequence_number=0, text="calculating", start_time=0.0, end_time=0.5, is_final=False)
    seg_final = TranscriptSegment(segment_id="s1", sequence_number=0, text="calculate sum 10 20", start_time=0.0, end_time=1.0, is_final=True)

    evt_interim1 = TranscriptEvent(
        event_id="evt_1",
        session_id=session_id,
        event_type=TranscriptEventType.INTERIM,
        timestamp=100.0,
        segment=seg_interim,
    )
    # Duplicate interim event
    evt_interim_dup = TranscriptEvent(
        event_id="evt_1",
        session_id=session_id,
        event_type=TranscriptEventType.INTERIM,
        timestamp=100.0,
        segment=seg_interim,
    )
    evt_final = TranscriptEvent(
        event_id="evt_2",
        session_id=session_id,
        event_type=TranscriptEventType.FINAL,
        timestamp=101.0,
        segment=seg_final,
    )

    out1 = dedup.process_events([evt_interim1, evt_interim_dup])
    assert len(out1) == 1
    assert dedup.num_duplicates_suppressed == 1

    out2 = dedup.process_events([evt_final])
    assert len(out2) == 1
    assert dedup.num_interims_reconciled == 1

    finals = dedup.get_ordered_finals()
    assert len(finals) == 1
    assert finals[0].text == "calculate sum 10 20"
