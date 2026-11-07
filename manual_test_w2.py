"""Standalone manual testing script for Week 2 (Audio & VAD).

Runs entirely in mock mode without physical microphone, network, or external APIs.
Validates all major features and edge cases with clear PASS/FAIL reporting.

Usage:
    python manual_test_w2.py
"""

from __future__ import annotations

import math
import sys
from array import array
from typing import Callable, List, Tuple

from academia_audio import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
    AudioPipeline,
    BoundedAudioBuffer,
    DeviceInfo,
    LifecycleState,
    MockDeviceAdapter,
    MockVAD,
    OverflowStrategy,
    PermissionState,
    compute_rms,
)

FMT = AudioFormat(16000, 1)


def make_chunk(seq: int, pcm: bytes, timestamp: float | None = None) -> AudioChunk:
    ts = timestamp if timestamp is not None else seq * 0.02
    return AudioChunk(
        sequence_id=seq,
        timestamp_s=ts,
        format=FMT,
        data=pcm,
    )


def make_silence(seq: int) -> AudioChunk:
    return make_chunk(seq, b"\x00\x00" * 320)


def make_tone(seq: int, amplitude: float = 0.5, freq: float = 440.0) -> AudioChunk:
    peak = int(amplitude * 32767)
    samples = array("h")
    for n in range(320):
        t = (seq * 320 + n) / 16000
        samples.append(int(peak * math.sin(2 * math.pi * freq * t)))
    return make_chunk(seq, samples.tobytes())


def make_noise(seq: int, amplitude: float = 0.01) -> AudioChunk:
    return make_tone(seq, amplitude=amplitude, freq=150.0)


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
    print("=" * 72)
    print("  ACADEMIA AI VOICE BOT - WEEK 2 AUDIO & VAD MANUAL TEST SUITE")
    print("  Mode: 100% Mock Mode (Zero Hardware / Zero API / Stdlib Only)")
    print("=" * 72)

    runner = TestRunner()

    # --------------------------------------------------------------------------
    # 1. Device Adapter & Permissions
    # --------------------------------------------------------------------------
    print("\n[Section 1: Device Adapter & Permission States]")

    def test_device_selection():
        adapter = MockDeviceAdapter()
        devs = adapter.list_devices()
        adapter.select_device("mock-studio")
        sel = adapter.get_selected_device()
        ok = len(devs) >= 2 and sel.id == "mock-studio"
        return ok, f"Listed {len(devs)} devices; selected {sel.name}"

    runner.check("Device Selection", test_device_selection)

    def test_permission_denied():
        adapter = MockDeviceAdapter(permission_state=PermissionState.DENIED)
        try:
            adapter.open(FMT)
            return False, "Expected AudioError on denied permission, but open succeeded"
        except AudioError as err:
            ok = err.code == AudioErrorCode.PERMISSION_DENIED
            return ok, f"Handled gracefully with code={err.code.value} (no crash)"

    runner.check("Permission Denied (No Crash)", test_permission_denied)

    def test_device_unsupported():
        adapter = MockDeviceAdapter()
        try:
            adapter.select_device("mock-unsupported")
            return False, "Expected AudioError for unsupported device"
        except AudioError as err:
            ok = err.code == AudioErrorCode.DEVICE_UNSUPPORTED
            return ok, f"Handled gracefully with code={err.code.value} (no crash)"

    runner.check("Unsupported Device (No Crash)", test_device_unsupported)

    # --------------------------------------------------------------------------
    # 2. Audio Lifecycle & State Transitions
    # --------------------------------------------------------------------------
    print("\n[Section 2: Audio Lifecycle State Machine]")

    def test_lifecycle_happy_path():
        pipeline = AudioPipeline()
        s0 = pipeline.state
        pipeline.start()
        s1 = pipeline.state
        pipeline.pause()
        s2 = pipeline.state
        pipeline.resume()
        s3 = pipeline.state
        pipeline.stop()
        s4 = pipeline.state
        ok = (
            s0 == LifecycleState.STOPPED
            and s1 == LifecycleState.RUNNING
            and s2 == LifecycleState.PAUSED
            and s3 == LifecycleState.RUNNING
            and s4 == LifecycleState.STOPPED
        )
        return ok, "Transitions: STOPPED -> RUNNING -> PAUSED -> RUNNING -> STOPPED"

    runner.check("Lifecycle Normal Flow", test_lifecycle_happy_path)

    def test_illegal_transitions():
        pipeline = AudioPipeline()
        # From STOPPED, pause/resume/stop are illegal
        caught = []
        for action, name in [
            (pipeline.pause, "pause"),
            (pipeline.resume, "resume"),
            (pipeline.stop, "stop"),
        ]:
            try:
                action()
            except AudioError as e:
                if e.code == AudioErrorCode.ILLEGAL_STATE_TRANSITION:
                    caught.append(name)

        pipeline.start()
        # From RUNNING, start/resume are illegal
        for action, name in [(pipeline.start, "start"), (pipeline.resume, "resume")]:
            try:
                action()
            except AudioError as e:
                if e.code == AudioErrorCode.ILLEGAL_STATE_TRANSITION:
                    caught.append(name)

        pipeline.stop()
        ok = len(caught) == 5
        return ok, f"Successfully rejected {len(caught)} illegal state transitions"

    runner.check("Illegal Transitions Rejected", test_illegal_transitions)

    def test_stop_releases_buffer():
        buffer = BoundedAudioBuffer(capacity=10)
        pipeline = AudioPipeline(buffer=buffer)
        pipeline.start()
        pipeline.process_chunk(make_silence(0))
        pipeline.process_chunk(make_silence(1))
        size_before = pipeline.buffer.size
        pipeline.stop()
        size_after = pipeline.buffer.size
        ok = size_before == 2 and size_after == 0 and pipeline.buffer.is_empty
        return ok, f"Buffer size before stop={size_before}, after stop={size_after}"

    runner.check("Stop Releases Buffer", test_stop_releases_buffer)

    # --------------------------------------------------------------------------
    # 3. Voice Activity Detection (VAD)
    # --------------------------------------------------------------------------
    print("\n[Section 3: Voice Activity Detection (VAD)]")

    def test_vad_silence_rejection():
        vad = MockVAD(energy_threshold=0.05)
        res = vad.process_chunk(make_silence(0))
        ok = res.is_speech is False and res.energy == 0.0
        return ok, f"Silence rejected: is_speech={res.is_speech}, energy={res.energy}"

    runner.check("VAD Silence Non-Speech", test_vad_silence_rejection)

    def test_vad_background_noise():
        vad = MockVAD(energy_threshold=0.05)
        res = vad.process_chunk(make_noise(0, amplitude=0.01))
        ok = res.is_speech is False and res.energy < 0.05
        return ok, f"Background noise rejected: is_speech={res.is_speech}, RMS={res.energy:.4f} < 0.05"

    runner.check("VAD Background Noise Filtered", test_vad_background_noise)

    def test_vad_transient_filtering():
        vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=60.0)
        # Single 20ms click: energy is high, but duration < 60ms
        res = vad.process_chunk(make_tone(0, amplitude=0.5))
        ok = res.is_speech is False and res.energy > 0.3
        return ok, f"20ms transient spike ignored: is_speech={res.is_speech} (duration < 60ms)"

    runner.check("VAD Transient Spike Ignored", test_vad_transient_filtering)

    def test_vad_sustained_speech():
        vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=60.0)
        # 3 consecutive 20ms chunks reaches 60ms
        vad.process_chunk(make_tone(0, amplitude=0.5))
        vad.process_chunk(make_tone(1, amplitude=0.5))
        res3 = vad.process_chunk(make_tone(2, amplitude=0.5))
        ok = res3.is_speech is True and res3.speech_duration_s == 0.06
        return ok, f"Sustained speech recognized: is_speech={res3.is_speech}, duration={res3.speech_duration_s}s"

    runner.check("VAD Sustained Speech Detected", test_vad_sustained_speech)

    def test_vad_determinism():
        vad1 = MockVAD(energy_threshold=0.05, min_speech_duration_ms=40.0)
        vad2 = MockVAD(energy_threshold=0.05, min_speech_duration_ms=40.0)
        chunks = [make_silence(0), make_tone(1), make_tone(2), make_silence(3)]
        r1 = [vad1.process_chunk(c) for c in chunks]
        r2 = [vad2.process_chunk(c) for c in chunks]
        ok = r1 == r2
        return ok, "100% deterministic: duplicate runs produced identical VAD outputs"

    runner.check("VAD Determinism", test_vad_determinism)

    # --------------------------------------------------------------------------
    # 4. Bounded Buffer & Backpressure
    # --------------------------------------------------------------------------
    print("\n[Section 4: Bounded Buffer & Backpressure]")

    def test_buffer_capacity_bounded():
        buf = BoundedAudioBuffer(capacity=3, overflow_strategy=OverflowStrategy.DROP_OLDEST)
        for i in range(10):
            buf.push(make_silence(i))
        ok = buf.size == 3 and buf.dropped_chunks == 7
        return ok, f"Capacity bounded: max 3 chunks, dropped {buf.dropped_chunks} on overflow"

    runner.check("Buffer Capacity & Backpressure", test_buffer_capacity_bounded)

    def test_buffer_drop_oldest_order():
        buf = BoundedAudioBuffer(capacity=2, overflow_strategy=OverflowStrategy.DROP_OLDEST)
        buf.push(make_silence(0))
        buf.push(make_silence(1))
        buf.push(make_silence(2))  # Drops 0, keeps 1 and 2
        c1 = buf.pop()
        c2 = buf.pop()
        ok = c1.sequence_id == 1 and c2.sequence_id == 2 and buf.is_empty
        return ok, f"Preserved recent chunks: seq {c1.sequence_id} and {c2.sequence_id}"

    runner.check("Drop Oldest Strategy", test_buffer_drop_oldest_order)

    def test_buffer_cleanup():
        buf = BoundedAudioBuffer(capacity=5)
        for i in range(4):
            buf.push(make_silence(i))
        buf.clear()
        ok = buf.size == 0 and buf.is_empty and buf.pop() is None
        return ok, "Cleanup successfully released all chunk references"

    runner.check("Buffer Cleanup", test_buffer_cleanup)

    # --------------------------------------------------------------------------
    # 5. Temporal & Stream Edge Cases
    # --------------------------------------------------------------------------
    print("\n[Section 5: Stream Edge Cases (Gaps & Late Chunks)]")

    def test_audio_gap_detection():
        pipeline = AudioPipeline()
        pipeline.start()
        pipeline.process_chunk(make_silence(0))
        pipeline.process_chunk(make_silence(4))  # Missing 1, 2, 3
        gaps = pipeline.gaps_detected
        pipeline.stop()
        ok = gaps == 1
        return ok, f"Audio gap detected successfully: gap count = {gaps}"

    runner.check("Audio Gap Detection", test_audio_gap_detection)

    def test_late_chunk_rejection():
        pipeline = AudioPipeline()
        pipeline.start()
        pipeline.process_chunk(make_chunk(5, b"\x00\x00" * 320, timestamp=0.10))
        try:
            pipeline.process_chunk(make_chunk(3, b"\x00\x00" * 320, timestamp=0.06))
            return False, "Expected AudioError on late chunk"
        except AudioError as err:
            ok = err.code == AudioErrorCode.OUT_OF_ORDER
            pipeline.stop()
            return ok, f"Late chunk rejected with code={err.code.value}"

    runner.check("Late Chunk Rejection", test_late_chunk_rejection)

    # --------------------------------------------------------------------------
    # Final Summary
    # --------------------------------------------------------------------------
    print("\n" + "=" * 72)
    print(f"  RESULTS: Total Tests: {runner.passed + runner.failed} | Passed: {runner.passed} | Failed: {runner.failed}")
    if runner.failed == 0:
        print("  STATUS: ALL WEEK 2 ACCEPTANCE CRITERIA SATISFIED [PASS]")
        print("=" * 72)
        return 0
    else:
        print("  STATUS: SOME TESTS FAILED [FAIL]", file=sys.stderr)
        print("=" * 72, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run_manual_tests())
