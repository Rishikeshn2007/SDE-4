"""Standalone manual testing script for Week 3 (Audio & VAD).

Requirements:
- Runs entirely in mock mode without a physical microphone.
- Demonstrates speech-start/end event ordering.
- Displays session and correlation IDs.
- Simulates device loss and successful reconnection.
- Tests cancellation and buffer cleanup.
- Demonstrates audio-to-transcription event delivery.
- Tests gaps, silence and false triggers.
- Prints clear PASS/FAIL results for every scenario.
- Exits with a non-zero status if any test fails.

Usage:
    python scripts/manual_week3_test.py
"""

from __future__ import annotations

import math
import sys
from array import array
from pathlib import Path
from typing import Callable, List, Tuple

# Ensure repository root is on sys.path regardless of execution cwd
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from academia_audio import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioEventType,
    AudioFormat,
    AudioPipeline,
    BoundedAudioBuffer,
    DeviceDisconnectedEvent,
    DeviceReconnectedEvent,
    LifecycleState,
    MockDeviceAdapter,
    MockTranscriptionAdapter,
    MockVAD,
    SessionCancelledEvent,
    SpeechEndEvent,
    SpeechStartEvent,
    TranscriptionBridge,
    normalize_audio_chunk,
)

FMT = AudioFormat(16000, 1)


def make_pcm_tone(duration_s: float = 0.02, sample_rate: int = 16000, freq: float = 440.0, amp: int = 18000) -> bytes:
    """Deterministic 16-bit PCM tone generator."""
    num_samples = int(duration_s * sample_rate)
    raw = bytearray()
    for i in range(num_samples):
        val = int(amp * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
        raw.extend(val.to_bytes(2, byteorder="little", signed=True))
    return bytes(raw)


def make_pcm_silence(duration_s: float = 0.02, sample_rate: int = 16000) -> bytes:
    """Deterministic 16-bit PCM silence generator."""
    return b"\x00\x00" * int(duration_s * sample_rate)


def make_chunk(seq: int, is_speech: bool = False, timestamp: float | None = None) -> AudioChunk:
    ts = timestamp if timestamp is not None else round(seq * 0.02, 4)
    data = make_pcm_tone(duration_s=0.02) if is_speech else make_pcm_silence(duration_s=0.02)
    return AudioChunk(
        sequence_id=seq,
        timestamp_s=ts,
        format=FMT,
        data=data,
    )


class TestRunner:
    def __init__(self) -> None:
        self.passed: int = 0
        self.failed: int = 0
        self.results: List[Tuple[str, bool, str]] = []

    def check(self, name: str, fn: Callable[[], Tuple[bool, str]]) -> None:
        try:
            ok, detail = fn()
            if ok:
                self.passed += 1
                self.results.append((name, True, detail))
                print(f"  [PASS] {name} - {detail}")
            else:
                self.failed += 1
                self.results.append((name, False, detail))
                print(f"  [FAIL] {name} - {detail}", file=sys.stderr)
        except Exception as e:
            self.failed += 1
            self.results.append((name, False, f"Unexpected exception: {e}"))
            print(f"  [FAIL] {name} - Unexpected exception: {e}", file=sys.stderr)


def run_manual_tests() -> int:
    print("=" * 76)
    print("  ACADEMIA AI VOICE BOT - WEEK 3 AUDIO & VAD MANUAL TEST SUITE")
    print("  Mode: 100% Mock Mode (Zero Hardware / Zero API / Stdlib Only)")
    print("=" * 76)

    runner = TestRunner()

    # --------------------------------------------------------------------------
    # Section 1: Speech-Start / Speech-End Event Ordering
    # --------------------------------------------------------------------------
    print("\n[Section 1: Speech-Start / Speech-End Event Ordering]")

    def test_event_ordering():
        vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=40.0)
        chunks = [
            make_chunk(0, is_speech=False),
            make_chunk(1, is_speech=False),
            make_chunk(2, is_speech=True),
            make_chunk(3, is_speech=True),
            make_chunk(4, is_speech=True),
            make_chunk(5, is_speech=False),
            make_chunk(6, is_speech=False),
        ]
        adapter = MockDeviceAdapter(chunks=chunks)
        pipeline = AudioPipeline(adapter=adapter, vad=vad)
        pipeline.start(session_id="sess_ordering_demo", correlation_id="corr_ordering_demo")
        pipeline.run_steps()
        pipeline.stop()

        types = [e.event_type for e in pipeline.events]
        if AudioEventType.SPEECH_START not in types or AudioEventType.SPEECH_END not in types:
            return False, f"Missing speech events in {types}"

        start_idx = types.index(AudioEventType.SPEECH_START)
        end_idx = types.index(AudioEventType.SPEECH_END)

        if start_idx >= end_idx:
            return False, f"SPEECH_START (idx={start_idx}) occurred after SPEECH_END (idx={end_idx})"

        # Verify monotonicity of sequence_id
        seqs = [e.sequence_id for e in pipeline.events]
        if seqs != list(range(len(pipeline.events))):
            return False, f"Non-monotonic sequence IDs: {seqs}"

        return True, f"SPEECH_START @ step {start_idx} -> SPEECH_END @ step {end_idx}; sequence IDs strictly monotonic (0..{len(seqs)-1})"

    runner.check("Speech Event Ordering", test_event_ordering)

    # --------------------------------------------------------------------------
    # Section 2: Session ID and Correlation ID Propagation
    # --------------------------------------------------------------------------
    print("\n[Section 2: Session & Correlation ID Propagation]")

    def test_id_propagation():
        vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=20.0)
        chunks = [make_chunk(0, is_speech=False), make_chunk(1, is_speech=True), make_chunk(2, is_speech=False)]
        adapter = MockDeviceAdapter(chunks=chunks)
        pipeline = AudioPipeline(adapter=adapter, vad=vad)

        test_sess = "session-academia-w3-001"
        test_corr = "corr-distributed-trace-999"
        pipeline.start(session_id=test_sess, correlation_id=test_corr)
        pipeline.run_steps()
        pipeline.stop()

        all_match = all(e.session_id == test_sess and e.correlation_id == test_corr for e in pipeline.events)
        if not all_match:
            return False, "Not all events contained matching session_id and correlation_id"

        sample = pipeline.events[0]
        return True, f"Verified across {len(pipeline.events)} events: session_id='{sample.session_id}', correlation_id='{sample.correlation_id}'"

    runner.check("ID Propagation", test_id_propagation)

    # --------------------------------------------------------------------------
    # Section 3: Device Loss & Safe Reconnection Recovery
    # --------------------------------------------------------------------------
    print("\n[Section 3: Device Loss & Safe Reconnection Recovery]")

    def test_device_loss_recovery():
        adapter = MockDeviceAdapter()
        pipeline = AudioPipeline(adapter=adapter, auto_reconnect=True)
        pipeline.start(session_id="sess_loss_demo", correlation_id="corr_loss_demo")

        # Step 1: Normal
        r1 = pipeline.step()
        if r1 is None:
            return False, "Initial step failed"

        # Simulate device disconnection mid-session
        adapter.simulate_disconnect(reason="Physical USB unplug simulated")

        # Step 2: Device loss detected, auto-reconnected safely without crashing
        r2 = pipeline.step()
        pipeline.stop()

        disc_evts = [e for e in pipeline.events if e.event_type == AudioEventType.DEVICE_DISCONNECTED]
        reconn_evts = [e for e in pipeline.events if e.event_type == AudioEventType.DEVICE_RECONNECTED]

        if not disc_evts or not reconn_evts:
            return False, f"Missing device events (disc={len(disc_evts)}, reconn={len(reconn_evts)})"

        return True, f"Detected disconnect ('{disc_evts[0].reason}') -> Successfully reconnected without crashing (reconnections={pipeline.device_reconnections_successful})"

    runner.check("Device Loss Recovery", test_device_loss_recovery)

    # --------------------------------------------------------------------------
    # Section 4: Cancellation & Buffer Cleanup
    # --------------------------------------------------------------------------
    print("\n[Section 4: Cancellation & Buffer Cleanup]")

    def test_cancellation_and_buffer_cleanup():
        buffer = BoundedAudioBuffer(capacity=10)
        pipeline = AudioPipeline(buffer=buffer)
        pipeline.start(session_id="sess_cancel_demo")

        pipeline.process_chunk(make_chunk(0))
        pipeline.process_chunk(make_chunk(1))
        size_before = pipeline.buffer.size
        if size_before != 2:
            return False, f"Expected buffer size 2 before cancel, got {size_before}"

        pipeline.cancel(reason="User invoked stop action")
        size_after = pipeline.buffer.size
        state = pipeline.state

        if size_after != 0:
            return False, f"Buffer not empty after cancel: {size_after}"
        if state != LifecycleState.CANCELLED:
            return False, f"Pipeline not in CANCELLED state: {state}"

        cancel_events = [e for e in pipeline.events if e.event_type == AudioEventType.SESSION_CANCELLED]
        if not cancel_events:
            return False, "Missing SessionCancelledEvent"

        return True, f"Buffer size {size_before} -> {size_after} (released); Pipeline state: {state.value}; Cancel event logged"

    runner.check("Cancellation & Buffer Cleanup", test_cancellation_and_buffer_cleanup)

    # --------------------------------------------------------------------------
    # Section 5: End-to-End Transcription Integration
    # --------------------------------------------------------------------------
    print("\n[Section 5: End-to-End Transcription Integration]")

    def test_transcription_integration():
        vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=40.0)
        chunks = [
            make_chunk(0, is_speech=False),
            make_chunk(1, is_speech=True),
            make_chunk(2, is_speech=True),
            make_chunk(3, is_speech=True),
            make_chunk(4, is_speech=False),
        ]
        adapter = MockDeviceAdapter(chunks=chunks)
        pipeline = AudioPipeline(adapter=adapter, vad=vad)

        transcriber = MockTranscriptionAdapter(canned_transcript="academia voice assistant connected")
        bridge = TranscriptionBridge(transcriber=transcriber)
        pipeline.attach_transcription_sink(bridge)

        pipeline.start(session_id="sess_transcription_demo")
        pipeline.run_steps()
        pipeline.stop()

        transcript = bridge.get_transcript_text()
        events_count = len(bridge.transcript_events)

        if not transcript or events_count == 0:
            return False, f"No transcript events produced (count={events_count}, text='{transcript}')"

        return True, f"Delivered {bridge.total_speech_chunks_forwarded} speech chunks -> Transcribed '{transcript}' ({events_count} events)"

    runner.check("Audio-to-Transcription Delivery", test_transcription_integration)

    # --------------------------------------------------------------------------
    # Section 6: Edge Cases: Gaps, Silence & False Triggers
    # --------------------------------------------------------------------------
    print("\n[Section 6: Robustness Edge Cases (Gaps, Silence, False Triggers)]")

    def test_silence_handling():
        pipeline = AudioPipeline(vad=MockVAD())
        pipeline.start(session_id="sess_silence_demo")
        for i in range(4):
            pipeline.process_chunk(make_chunk(i, is_speech=False))
        pipeline.stop()

        speech_events = [e for e in pipeline.events if e.event_type in (AudioEventType.SPEECH_START, AudioEventType.SPEECH_END)]
        if speech_events:
            return False, f"False speech events emitted on silence: {speech_events}"
        return True, "4 silence chunks evaluated -> 0 false speech triggers emitted"

    def test_transient_noise_rejection():
        vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=60.0)
        pipeline = AudioPipeline(vad=vad)
        pipeline.start(session_id="sess_transient_demo")
        # 1 spike of 20ms (< 60ms threshold)
        pipeline.process_chunk(make_chunk(0, is_speech=False))
        pipeline.process_chunk(make_chunk(1, is_speech=True))
        pipeline.process_chunk(make_chunk(2, is_speech=False))
        pipeline.stop()

        speech_events = [e for e in pipeline.events if e.event_type in (AudioEventType.SPEECH_START, AudioEventType.SPEECH_END)]
        if speech_events:
            return False, f"Transient click triggered speech events: {speech_events}"
        return True, "20ms acoustic click ignored (< 60ms threshold) -> No false speech event"

    def test_gap_detection():
        pipeline = AudioPipeline(strict_gap_detection=False)
        pipeline.start(session_id="sess_gaps_demo")
        pipeline.process_chunk(make_chunk(0))
        # Jump seq 0 -> seq 5 (missing 1, 2, 3, 4)
        pipeline.process_chunk(make_chunk(5, timestamp=0.10))
        pipeline.stop()

        if pipeline.gaps_detected != 1:
            return False, f"Expected 1 gap detected, got {pipeline.gaps_detected}"
        return True, f"Successfully detected missing sequence gap (count={pipeline.gaps_detected})"

    runner.check("Pure Silence Handling", test_silence_handling)
    runner.check("False Trigger Rejection", test_transient_noise_rejection)
    runner.check("Audio Gap Detection", test_gap_detection)

    # --------------------------------------------------------------------------
    # Final Summary
    # --------------------------------------------------------------------------
    print("\n" + "=" * 76)
    print(f"  RESULTS: Total Tests: {runner.passed + runner.failed} | Passed: {runner.passed} | Failed: {runner.failed}")
    if runner.failed == 0:
        print("  STATUS: ALL WEEK 3 ACCEPTANCE CRITERIA SATISFIED [PASS]")
        print("=" * 76)
        return 0
    else:
        print("  STATUS: SOME TESTS FAILED [FAIL]", file=sys.stderr)
        print("=" * 76)
        return 1


if __name__ == "__main__":
    sys.exit(run_manual_tests())
