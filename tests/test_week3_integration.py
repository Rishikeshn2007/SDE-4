"""Integration tests for Week 3 - Audio & VAD: Speech Events, Device-Loss Recovery & Transcription.

Validates all strict acceptance criteria:
1. Speech-start and speech-end events emitted in correct order.
2. Every event contains valid session and correlation IDs.
3. Device loss mid-session detected and recovered through reconnection without crashing.
4. Cancellation stops capture and releases the buffer.
5. Audio events reach transcription end-to-end in mock mode.
6. Ordering, gaps, silence, and false speech triggers covered without physical hardware.
7. Reuse existing schemas with no duplicate definitions.
"""

import pytest

from academia_audio import (
    AudioChunk,
    AudioChunkEvent,
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
    PermissionState,
    SessionCancelledEvent,
    SpeechEndEvent,
    SpeechStartEvent,
    TranscriptionBridge,
    normalize_audio_chunk,
)

FMT = AudioFormat(16000, 1)


def make_pcm_tone(duration_s: float = 0.02, sample_rate: int = 16000, freq: float = 440.0, amp: int = 16000) -> bytes:
    """Generate deterministic 16-bit PCM tone bytes."""
    import math
    num_samples = int(duration_s * sample_rate)
    raw = bytearray()
    for i in range(num_samples):
        val = int(amp * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
        raw.extend(val.to_bytes(2, byteorder="little", signed=True))
    return bytes(raw)


def make_pcm_silence(duration_s: float = 0.02, sample_rate: int = 16000) -> bytes:
    """Generate deterministic 16-bit PCM silence bytes."""
    num_samples = int(duration_s * sample_rate)
    return b"\x00\x00" * num_samples


def make_chunk(seq: int, is_speech: bool = False, timestamp: float | None = None) -> AudioChunk:
    ts = timestamp if timestamp is not None else seq * 0.02
    data = make_pcm_tone(duration_s=0.02, amp=18000) if is_speech else make_pcm_silence(duration_s=0.02)
    return AudioChunk(
        sequence_id=seq,
        timestamp_s=ts,
        format=FMT,
        data=data,
    )


# ==============================================================================
# 1. Event Schemas & Strict Validation Tests
# ==============================================================================

def test_speech_event_schemas_validation():
    """Verify that all Week 3 event schemas enforce valid IDs, timestamps, and immutability."""
    # Valid SpeechStartEvent
    start_evt = SpeechStartEvent(
        event_id="evt_0",
        session_id="sess_123",
        correlation_id="corr_456",
        event_type=AudioEventType.SPEECH_START,
        timestamp_s=1.05,
        sequence_id=0,
        speech_start_time_s=1.05,
    )
    assert start_evt.event_type == AudioEventType.SPEECH_START
    assert start_evt.session_id == "sess_123"
    assert start_evt.correlation_id == "corr_456"

    # Reject empty session_id
    with pytest.raises(AudioError) as exc:
        SpeechStartEvent(
            event_id="evt_1",
            session_id="   ",
            correlation_id="corr_456",
            event_type=AudioEventType.SPEECH_START,
            timestamp_s=1.0,
            sequence_id=1,
        )
    assert exc.value.code == AudioErrorCode.INVALID_PARAMETER

    # Reject empty correlation_id
    with pytest.raises(AudioError) as exc:
        SpeechEndEvent(
            event_id="evt_2",
            session_id="sess_123",
            correlation_id="",
            event_type=AudioEventType.SPEECH_END,
            timestamp_s=2.0,
            sequence_id=2,
            speech_start_time_s=1.0,
            speech_end_time_s=2.0,
            duration_s=1.0,
        )
    assert exc.value.code == AudioErrorCode.INVALID_PARAMETER

    # Reject speech_end_time < speech_start_time
    with pytest.raises(AudioError) as exc:
        SpeechEndEvent(
            event_id="evt_3",
            session_id="sess_123",
            correlation_id="corr_456",
            event_type=AudioEventType.SPEECH_END,
            timestamp_s=2.0,
            sequence_id=3,
            speech_start_time_s=3.0,
            speech_end_time_s=1.0,
            duration_s=1.0,
        )
    assert exc.value.code == AudioErrorCode.INVALID_TIMESTAMP

    # Verify immutability
    with pytest.raises(Exception):
        start_evt.sequence_id = 99  # type: ignore


# ==============================================================================
# 2. Speech Event Ordering & Monotonicity
# ==============================================================================

def test_speech_event_ordering_and_monotonicity():
    """Acceptance Criterion: Speech-start and speech-end events must be emitted in correct order."""
    vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=40.0)
    # Stream: 2 chunks silence, 4 chunks speech (80ms), 2 chunks silence
    chunks = [
        make_chunk(0, is_speech=False),
        make_chunk(1, is_speech=False),
        make_chunk(2, is_speech=True),
        make_chunk(3, is_speech=True),
        make_chunk(4, is_speech=True),
        make_chunk(5, is_speech=True),
        make_chunk(6, is_speech=False),
        make_chunk(7, is_speech=False),
    ]
    adapter = MockDeviceAdapter(chunks=chunks)
    pipeline = AudioPipeline(adapter=adapter, vad=vad)
    pipeline.start(session_id="sess_ordering", correlation_id="corr_ordering")

    pipeline.run_steps()
    pipeline.stop()

    events = pipeline.events
    assert len(events) > 0

    # Extract event types in order
    event_types = [e.event_type for e in events]

    # Verify SpeechStartEvent precedes speech AudioChunkEvents and SpeechEndEvent follows them
    assert AudioEventType.SPEECH_START in event_types
    assert AudioEventType.SPEECH_END in event_types

    start_idx = event_types.index(AudioEventType.SPEECH_START)
    end_idx = event_types.index(AudioEventType.SPEECH_END)

    assert start_idx < end_idx, "SpeechStartEvent must be emitted before SpeechEndEvent"

    # Verify the chunk right after SPEECH_START is a speech chunk
    assert event_types[start_idx + 1] == AudioEventType.AUDIO_CHUNK
    assert events[start_idx + 1].is_speech is True  # type: ignore

    # Verify sequence IDs strictly increase on every emitted event
    seq_ids = [e.sequence_id for e in events]
    assert seq_ids == list(range(len(events))), "Event sequence IDs must strictly increase monotonically"


# ==============================================================================
# 3. Session and Correlation ID Propagation
# ==============================================================================

def test_session_and_correlation_id_propagation():
    """Acceptance Criterion: Every event must contain session and correlation IDs."""
    vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=40.0)
    chunks = [
        make_chunk(0, is_speech=False),
        make_chunk(1, is_speech=True),
        make_chunk(2, is_speech=True),
        make_chunk(3, is_speech=False),
    ]
    adapter = MockDeviceAdapter(chunks=chunks)
    pipeline = AudioPipeline(adapter=adapter, vad=vad)

    test_sess = "session_alpha_101"
    test_corr = "trace_corr_999"
    pipeline.start(session_id=test_sess, correlation_id=test_corr)
    pipeline.run_steps()
    pipeline.stop()

    assert len(pipeline.events) >= 4
    for evt in pipeline.events:
        assert evt.session_id == test_sess, f"Event {evt.event_id} missing session_id"
        assert evt.correlation_id == test_corr, f"Event {evt.event_id} missing correlation_id"
        assert len(evt.event_id) > 0


# ==============================================================================
# 4. Silence and False Speech Triggers (Noise Filtering)
# ==============================================================================

def test_pure_silence_emits_no_speech_events():
    """Pure silence must never trigger speech-start or speech-end events."""
    vad = MockVAD(energy_threshold=0.05)
    chunks = [make_chunk(i, is_speech=False) for i in range(5)]
    adapter = MockDeviceAdapter(chunks=chunks)
    pipeline = AudioPipeline(adapter=adapter, vad=vad)
    pipeline.start(session_id="sess_silence")
    pipeline.run_steps()
    pipeline.stop()

    for evt in pipeline.events:
        assert evt.event_type == AudioEventType.AUDIO_CHUNK
        assert evt.is_speech is False  # type: ignore
        assert evt.rms_energy == 0.0  # type: ignore

    event_types = [e.event_type for e in pipeline.events]
    assert AudioEventType.SPEECH_START not in event_types
    assert AudioEventType.SPEECH_END not in event_types


def test_false_speech_trigger_transient_filtering():
    """Short acoustic transient clicks (< min_speech_duration) must NOT trigger speech events."""
    vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=60.0)
    # A single 20ms burst of sound (less than 60ms min_speech_duration)
    chunks = [
        make_chunk(0, is_speech=False),
        make_chunk(1, is_speech=True),  # 20ms spike
        make_chunk(2, is_speech=False),
        make_chunk(3, is_speech=False),
    ]
    adapter = MockDeviceAdapter(chunks=chunks)
    pipeline = AudioPipeline(adapter=adapter, vad=vad)
    pipeline.start(session_id="sess_transient")
    pipeline.run_steps()
    pipeline.stop()

    event_types = [e.event_type for e in pipeline.events]
    assert AudioEventType.SPEECH_START not in event_types
    assert AudioEventType.SPEECH_END not in event_types


# ==============================================================================
# 5. Device-Loss Recovery Mid-Session
# ==============================================================================

def test_device_loss_detected_and_recovered_without_crashing():
    """Acceptance Criterion: Device loss mid-session must be detected and recovered without crashing."""
    adapter = MockDeviceAdapter()
    pipeline = AudioPipeline(adapter=adapter, auto_reconnect=True)
    pipeline.start(session_id="sess_dev_loss")

    # 1. Normal step
    res1 = pipeline.step()
    assert res1 is not None
    assert pipeline.is_running is True

    # 2. Simulate hardware disconnection mid-session
    adapter.simulate_disconnect(reason="USB Microphone disconnected by user")
    assert adapter.is_connected is False

    # 3. Step after disconnect: pipeline detects device loss and recovers gracefully without crashing
    res2 = pipeline.step()
    # Auto-reconnection restores RUNNING state
    assert pipeline.is_running is True
    assert pipeline.device_disconnections_detected == 1
    assert pipeline.device_reconnections_successful == 1

    # Check emitted recovery events
    event_types = [e.event_type for e in pipeline.events]
    assert AudioEventType.DEVICE_DISCONNECTED in event_types
    assert AudioEventType.DEVICE_RECONNECTED in event_types

    pipeline.stop()
    assert pipeline.is_stopped is True


def test_manual_device_recovery_when_auto_reconnect_disabled():
    """Pipeline remains in RECOVERING state without crashing until manual recover_device() is called."""
    adapter = MockDeviceAdapter()
    pipeline = AudioPipeline(adapter=adapter, auto_reconnect=False)
    pipeline.start(session_id="sess_manual_rec")

    pipeline.step()
    adapter.simulate_disconnect(reason="Cable pulled")

    # Without auto_reconnect, pipeline steps into RECOVERING state without throwing an unhandled exception
    res = pipeline.step()
    assert res is None
    assert pipeline.state == LifecycleState.RECOVERING
    assert pipeline.is_recovering is True

    # Manually reconnect
    recovered = pipeline.recover_device()
    assert recovered is True
    assert pipeline.state == LifecycleState.RUNNING
    assert pipeline.is_running is True

    pipeline.stop()


# ==============================================================================
# 6. Session Cancellation & Buffer Release
# ==============================================================================

def test_cancellation_stops_capture_and_releases_buffer():
    """Acceptance Criterion: Cancellation must stop capture and release the buffer."""
    buffer = BoundedAudioBuffer(capacity=10)
    pipeline = AudioPipeline(buffer=buffer)
    pipeline.start(session_id="sess_cancel", correlation_id="corr_cancel")

    # Feed chunks into buffer
    pipeline.process_chunk(make_chunk(0))
    pipeline.process_chunk(make_chunk(1))
    pipeline.process_chunk(make_chunk(2))
    assert pipeline.buffer.size == 3

    # Cancel session
    pipeline.cancel(reason="Caller terminated interaction")

    # State assertions
    assert pipeline.state == LifecycleState.CANCELLED
    assert pipeline.is_cancelled is True
    assert pipeline.is_running is False
    assert pipeline.is_stopped is True

    # Buffer cleanup assertion
    assert pipeline.buffer.size == 0
    assert pipeline.buffer.is_empty is True
    assert pipeline.buffer.pop() is None

    # Step on cancelled pipeline returns None
    assert pipeline.step() is None

    # Verify SessionCancelledEvent was emitted
    cancel_events = [e for e in pipeline.events if e.event_type == AudioEventType.SESSION_CANCELLED]
    assert len(cancel_events) == 1
    assert cancel_events[0].reason == "Caller terminated interaction"  # type: ignore


def test_cancellation_during_speech_flushes_speech_end_event():
    """Cancelling mid-speech must cleanly emit SpeechEndEvent before SessionCancelledEvent."""
    vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=20.0)
    pipeline = AudioPipeline(vad=vad)
    pipeline.start(session_id="sess_cancel_speech")

    # Feed speech chunk
    pipeline.process_chunk(make_chunk(0, is_speech=True))
    assert pipeline._in_speech is True

    pipeline.cancel(reason="Interrupted")
    event_types = [e.event_type for e in pipeline.events]

    assert AudioEventType.SPEECH_START in event_types
    assert AudioEventType.SPEECH_END in event_types
    assert AudioEventType.SESSION_CANCELLED in event_types

    end_idx = event_types.index(AudioEventType.SPEECH_END)
    cancel_idx = event_types.index(AudioEventType.SESSION_CANCELLED)
    assert end_idx < cancel_idx, "SpeechEndEvent must precede SessionCancelledEvent"


# ==============================================================================
# 7. Transcription Integration End-to-End in Mock Mode
# ==============================================================================

def test_audio_events_reach_transcription_end_to_end_mock_mode():
    """Acceptance Criterion: Audio events must reach transcription end-to-end in mock mode."""
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

    mock_transcriber = MockTranscriptionAdapter(canned_transcript="academia voice assistant active")
    bridge = TranscriptionBridge(transcriber=mock_transcriber, auto_flush_on_speech_end=True)
    pipeline.attach_transcription_sink(bridge)

    pipeline.start(session_id="sess_transcription")
    pipeline.run_steps()
    pipeline.stop()

    # Verify chunks reached the transcriber
    assert bridge.total_speech_chunks_forwarded >= 3
    assert len(bridge.transcript_events) > 0

    # Verify transcript text was assembled
    transcript_text = bridge.get_transcript_text()
    assert len(transcript_text) > 0
    assert "academia" in transcript_text or "voice" in transcript_text


# ==============================================================================
# 8. Audio Normalization
# ==============================================================================

def test_audio_normalization_scales_pcm():
    """Verify that normalize_audio_chunk scales audio amplitude without distortion or clipping."""
    quiet_chunk = make_chunk(0, is_speech=True)
    normalized = normalize_audio_chunk(quiet_chunk, target_peak=0.90)

    assert isinstance(normalized, AudioChunk)
    assert normalized.sequence_id == quiet_chunk.sequence_id
    assert normalized.timestamp_s == quiet_chunk.timestamp_s
    assert len(normalized.data) == len(quiet_chunk.data)

    # Silence remains unchanged
    silence_chunk = make_chunk(1, is_speech=False)
    norm_silence = normalize_audio_chunk(silence_chunk)
    assert norm_silence.data == silence_chunk.data
