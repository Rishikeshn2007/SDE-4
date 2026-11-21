import pytest

from academia_audio import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
    AudioPipeline,
    BoundedAudioBuffer,
    LifecycleState,
    MockDeviceAdapter,
    MockVAD,
    PermissionState,
)

FMT = AudioFormat(16000, 1)


def make_chunk(seq: int, timestamp: float | None = None) -> AudioChunk:
    ts = timestamp if timestamp is not None else seq * 0.02
    return AudioChunk(
        sequence_id=seq,
        timestamp_s=ts,
        format=FMT,
        data=b"\x00\x00" * 320,
    )


def test_lifecycle_happy_path():
    pipeline = AudioPipeline()
    assert pipeline.state == LifecycleState.STOPPED
    assert pipeline.is_stopped is True

    pipeline.start()
    assert pipeline.state == LifecycleState.RUNNING
    assert pipeline.is_running is True

    pipeline.pause()
    assert pipeline.state == LifecycleState.PAUSED
    assert pipeline.is_paused is True

    pipeline.resume()
    assert pipeline.state == LifecycleState.RUNNING
    assert pipeline.is_running is True

    pipeline.stop()
    assert pipeline.state == LifecycleState.STOPPED
    assert pipeline.is_stopped is True


def test_illegal_lifecycle_transitions():
    pipeline = AudioPipeline()

    # From STOPPED: pause, resume, stop are illegal
    with pytest.raises(AudioError) as exc:
        pipeline.pause()
    assert exc.value.code == AudioErrorCode.ILLEGAL_STATE_TRANSITION

    with pytest.raises(AudioError) as exc:
        pipeline.resume()
    assert exc.value.code == AudioErrorCode.ILLEGAL_STATE_TRANSITION

    with pytest.raises(AudioError) as exc:
        pipeline.stop()
    assert exc.value.code == AudioErrorCode.ILLEGAL_STATE_TRANSITION

    # Start -> RUNNING
    pipeline.start()

    # From RUNNING: start, resume are illegal
    with pytest.raises(AudioError) as exc:
        pipeline.start()
    assert exc.value.code == AudioErrorCode.ILLEGAL_STATE_TRANSITION

    with pytest.raises(AudioError) as exc:
        pipeline.resume()
    assert exc.value.code == AudioErrorCode.ILLEGAL_STATE_TRANSITION

    # Pause -> PAUSED
    pipeline.pause()

    # From PAUSED: start, pause are illegal
    with pytest.raises(AudioError) as exc:
        pipeline.start()
    assert exc.value.code == AudioErrorCode.ILLEGAL_STATE_TRANSITION

    with pytest.raises(AudioError) as exc:
        pipeline.pause()
    assert exc.value.code == AudioErrorCode.ILLEGAL_STATE_TRANSITION

    # Stop from PAUSED -> STOPPED
    pipeline.stop()
    assert pipeline.state == LifecycleState.STOPPED


def test_stop_releases_buffer():
    # Strict Acceptance Criterion: Stop releases the buffer.
    buffer = BoundedAudioBuffer(capacity=10)
    pipeline = AudioPipeline(buffer=buffer)
    pipeline.start()

    pipeline.process_chunk(make_chunk(0))
    pipeline.process_chunk(make_chunk(1))
    pipeline.process_chunk(make_chunk(2))
    assert pipeline.buffer.size == 3
    assert pipeline.buffer.is_empty is False

    pipeline.stop()
    assert pipeline.buffer.size == 0
    assert pipeline.buffer.is_empty is True
    assert pipeline.buffer.pop() is None


def test_permission_denied_on_start():
    adapter = MockDeviceAdapter(permission_state=PermissionState.DENIED)
    pipeline = AudioPipeline(adapter=adapter)

    with pytest.raises(AudioError) as exc:
        pipeline.start()
    assert exc.value.code == AudioErrorCode.PERMISSION_DENIED
    assert pipeline.state == LifecycleState.STOPPED


def test_audio_gaps_detection():
    pipeline = AudioPipeline(strict_gap_detection=False)
    pipeline.start()

    pipeline.process_chunk(make_chunk(0))
    # Gap: skip sequence 1, 2, 3 -> jump straight to 4
    pipeline.process_chunk(make_chunk(4))
    assert pipeline.gaps_detected == 1

    pipeline.stop()


def test_strict_audio_gaps_raises():
    pipeline = AudioPipeline(strict_gap_detection=True)
    pipeline.start()

    pipeline.process_chunk(make_chunk(0))
    with pytest.raises(AudioError) as exc:
        pipeline.process_chunk(make_chunk(3))
    assert exc.value.code == AudioErrorCode.AUDIO_GAP_DETECTED

    pipeline.stop()


def test_late_chunks_rejected():
    pipeline = AudioPipeline()
    pipeline.start()

    pipeline.process_chunk(make_chunk(5, timestamp=0.10))

    # Late chunk: seq 4 < 5
    with pytest.raises(AudioError) as exc:
        pipeline.process_chunk(make_chunk(4, timestamp=0.08))
    assert exc.value.code == AudioErrorCode.OUT_OF_ORDER
    assert pipeline.late_chunks_detected == 1

    # Late chunk: seq 5 == 5 (duplicate or late)
    with pytest.raises(AudioError) as exc:
        pipeline.process_chunk(make_chunk(5, timestamp=0.12))
    assert exc.value.code == AudioErrorCode.OUT_OF_ORDER

    pipeline.stop()


def test_pipeline_step_and_run_steps():
    adapter = MockDeviceAdapter(chunks=[make_chunk(0), make_chunk(1), make_chunk(2)])
    pipeline = AudioPipeline(adapter=adapter)
    pipeline.start()

    results = pipeline.run_steps()
    assert len(results) == 3
    assert pipeline.total_chunks_processed == 3
    assert results[0][0].sequence_id == 0
    assert results[1][0].sequence_id == 1
    assert results[2][0].sequence_id == 2

    pipeline.stop()
