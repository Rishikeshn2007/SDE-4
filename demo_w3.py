"""
SDE-4 Academia AI Voice Co-Pilot – Week 3 Day 21 End-to-End Integration Demo
=============================================================================

Demonstrates the full, resilient 11-step lifecycle completely offline:
1. Audio chunk ingestion (W1 AudioChunk stream)
2. Session initialization with Session ID preservation
3. Interim transcript emission
4. Dynamic transcript revision
5. Final transcript generation
6. Confidence threshold enforcement
7. W5 backend event stream publication
8. Reasoning layer intent extraction
9. Workflow plan construction
10. Consequential action approval gate (pause -> approval -> completion)
11. Clean shutdown and summary metrics display
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

from academia_audio.mock_source import MockMicrophone
from workflow.schemas import WorkflowState

from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.event_bridge import EventBridgePublisher
from sde4_stt.fallback import FallbackAdapter
from sde4_stt.orchestrator import TranscriptionOrchestrator
from sde4_stt.schemas.transcript import TranscriptEventType
from sde4_stt.session import SessionManager
from sde4_stt.workflow_bridge import VoiceWorkflowBridge
from tests.test_w3 import FailingAdapter


def banner(title: str) -> None:
    print(f"\n{'=' * 75}\n  {title}\n{'=' * 75}")


def main() -> None:
    banner("ACADEMIA AI VOICE CO-PILOT - WEEK 3 DAY 21 DEMONSTRATION")
    print("Architecture: W1 Audio -> STT Orchestrator -> W5 Event Stream -> Reasoning -> Approval Gate")
    print("Mode: 100% Offline, Deterministic, Zero External API Keys Required\n")

    # [1] Audio Chunk Ingestion & [2] Session Initialization
    banner("STEP 1 & 2: Audio Chunk Ingestion & Session Initialization")
    session_id = "session_day21_demo"
    session_mgr = SessionManager()
    session_ctx = session_mgr.create_session(session_id, confidence_threshold=0.80)

    print(f"[+] Initialized Session: '{session_ctx.session_id}'")
    print(f"[+] Configured Confidence Threshold: {session_ctx.confidence_threshold:.2f}")

    mic = MockMicrophone(duration_s=0.75, chunk_ms=250)
    audio_chunks = list(mic.stream())
    print(f"[+] Ingested {len(audio_chunks)} W1 AudioChunks (16kHz, 16-bit mono PCM).")
    for chunk in audio_chunks:
        print(f"    - Chunk {chunk.sequence_id}: timestamp={chunk.timestamp_s:.2f}s, size={len(chunk.data)} bytes")

    # W5 Backend Event Stream Mock
    w5_stream: List[Dict[str, Any]] = []

    def w5_backend_publish(sid: str, event_type: str, data: dict) -> None:
        w5_stream.append({
            "session_id": sid,
            "event_type": event_type,
            "data": data,
        })

    publisher = EventBridgePublisher(publish_fn=w5_backend_publish)

    # [3] Interim, [4] Revision, [5] Final
    banner("STEP 3, 4 & 5: Interim Emission, Dynamic Revision, Final Transcript")
    # Configured to emit:
    # Chunk 0 -> Interim: "calculate sum"
    # Chunk 1 -> Revised: "calculate sum 25 75"
    # Chunk 2 -> Final: "calculate sum 25 75"
    adapter = FakeTranscriber(
        canned_transcript="calculate sum 25 75",
        revision_at_chunk_index=1,
        revised_words=["calculate", "sum", "25", "75"],
        fixed_confidence=0.95,
    )

    orchestrator = TranscriptionOrchestrator(
        adapter=adapter,
        cancellation_token=session_ctx.cancellation_token,
        confidence_threshold=session_ctx.confidence_threshold,
        event_publisher=publisher,
    )

    result = orchestrator.transcribe(audio_chunks, session_id=session_ctx.session_id)

    print(f"[+] Transcription Completed in {result.duration_s * 1000:.1f}ms")
    print(f"[+] Final Recognized Text: \"{result.full_text}\"")
    print(f"[+] Segments Committed: {len(result.segments)}")
    print(f"[+] Duplicates Suppressed: {result.duplicates_suppressed}")
    print(f"[+] Interims Reconciled:   {result.interims_reconciled}")

    # [6] Confidence Threshold Enforcement
    banner("STEP 6: Confidence Threshold Enforcement")
    low_conf_events = [e for e in result.events if e.error and e.error.code == "LOW_CONFIDENCE"]
    print(f"[+] Segment Confidence: {result.segments[0].confidence:.2f}")
    print(f"[+] Threshold Required: {session_ctx.confidence_threshold:.2f}")
    if low_conf_events:
        print(f"[!] Low confidence warning triggered: {low_conf_events[0].error.message}")
    else:
        print("[+] Confidence ACCEPTED: Segment exceeds required threshold.")

    # [7] W5 Backend Event Stream Publication
    banner("STEP 7: W5 Backend Event Stream Publication")
    print(f"[+] Published {len(w5_stream)} events to W5 EventBridgePublisher with session '{session_id}':")
    for idx, item in enumerate(w5_stream, 1):
        payload_summary = ""
        if "segment" in item["data"] and item["data"]["segment"]:
            payload_summary = f"text='{item['data']['segment'].get('text')}'"
        elif "error" in item["data"] and item["data"]["error"]:
            payload_summary = f"err={item['data']['error'].get('code')}"
        print(f"    {idx}. [{item['event_type']}] session={item['session_id']} {payload_summary}")

    # [8] Reasoning & [9] Workflow Plan Construction
    banner("STEP 8 & 9: Reasoning Layer Intent Extraction & Workflow Plan")
    bridge = VoiceWorkflowBridge(event_publisher=publisher)
    plan = bridge.reason_and_plan(
        session_id=session_id,
        transcript_text=result.full_text,
        force_consequential=True,  # Simulate a consequential action requiring approval
    )

    print(f"[+] Plan ID: {plan.plan_id}")
    print(f"[+] Extracted Intent: execute '{plan.steps[0].tool_name}'")
    print(f"[+] Inputs Parsed: {plan.steps[0].inputs}")
    print(f"[+] Consequential Action Flag: {plan.steps[0].consequential}")

    # [10] Consequential Action Approval Gate
    banner("STEP 10: Consequential Action Approval Gate (Pause -> Approval -> Success)")
    print("[1] Executing plan without prior user approval...")
    stage1_res = bridge.execute(plan, session_id=session_id)

    print(f"    - State: {stage1_res.state.value.upper()}")
    assert stage1_res.state == WorkflowState.AWAITING_APPROVAL
    print(f"    - Paused at Approval Gate for step: '{stage1_res.approval_request.step_id}'")
    print(f"    - Description: {stage1_res.approval_request.description}")

    print("\n[2] User examines approval request and grants explicit approval...")
    approvals = {stage1_res.approval_request.step_id: True}
    stage2_res = bridge.execute(plan, session_id=session_id, approvals=approvals)

    print(f"    - State: {stage2_res.state.value.upper()}")
    assert stage2_res.state == WorkflowState.SUCCEEDED
    tool_output = stage2_res.step_results[0]["output"]
    print(f"    - Execution Output: {tool_output}")
    print(f"    - Computed Result: {tool_output.get('result')}")

    # [11] Summary Metrics Display & Clean Shutdown
    banner("STEP 11: Summary Metrics Display & Clean Shutdown")
    session_mgr.remove_session(session_id)
    print("Pipeline Execution Metrics:")
    print(f"  * Total Chunks Processed:       {result.chunks_processed}")
    print(f"  * STT Events Emitted:          {len(result.events)}")
    print(f"  * Total Backend Events Stream: {len(w5_stream)}")
    print(f"  * Active Sessions Remaining:   {len(session_mgr.active_sessions())}")
    print(f"  * End-to-End Status:           SUCCESS (All Day 21 gates passed)")
    banner("DEMONSTRATION COMPLETE")


if __name__ == "__main__":
    main()
