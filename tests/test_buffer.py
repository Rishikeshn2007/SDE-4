import pytest

from academia_audio import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
    BoundedAudioBuffer,
    OverflowStrategy,
)

FMT = AudioFormat(16000, 1)


def make_chunk(seq: int) -> AudioChunk:
    return AudioChunk(
        sequence_id=seq,
        timestamp_s=seq * 0.02,
        format=FMT,
        data=b"\x00\x00" * 320,
    )


def test_buffer_normal_operations():
    buf = BoundedAudioBuffer(capacity=5)
    assert buf.capacity == 5
    assert buf.size == 0
    assert buf.is_empty is True
    assert buf.is_full is False
    assert buf.dropped_chunks == 0

    c0 = make_chunk(0)
    c1 = make_chunk(1)

    assert buf.push(c0) is True
    assert buf.push(c1) is True
    assert buf.size == 2
    assert buf.is_empty is False
    assert buf.peek() == c0
    assert buf.total_bytes == 640 * 2
    assert buf.total_duration_s == pytest.approx(0.04)

    popped = buf.pop()
    assert popped == c0
    assert buf.size == 1
    assert buf.pop() == c1
    assert buf.pop() is None
    assert buf.is_empty is True


def test_buffer_invalid_params():
    with pytest.raises(AudioError) as exc:
        BoundedAudioBuffer(capacity=0)
    assert exc.value.code == AudioErrorCode.INVALID_PARAMETER

    with pytest.raises(AudioError) as exc:
        BoundedAudioBuffer(capacity=-10)
    assert exc.value.code == AudioErrorCode.INVALID_PARAMETER

    with pytest.raises(AudioError) as exc:
        buf = BoundedAudioBuffer(capacity=5)
        buf.push("not_a_chunk")  # type: ignore[arg-type]
    assert exc.value.code == AudioErrorCode.INVALID_DATA_TYPE


def test_buffer_overflow_drop_oldest():
    buf = BoundedAudioBuffer(capacity=3, overflow_strategy=OverflowStrategy.DROP_OLDEST)
    for i in range(3):
        assert buf.push(make_chunk(i)) is True

    assert buf.size == 3
    assert buf.is_full is True
    assert buf.dropped_chunks == 0

    # 4th chunk pushes out the oldest (chunk 0)
    c3 = make_chunk(3)
    pushed = buf.push(c3)
    assert pushed is False
    assert buf.size == 3  # Buffer remains strictly bounded!
    assert buf.dropped_chunks == 1

    # Remaining chunks should be 1, 2, 3
    assert buf.pop().sequence_id == 1
    assert buf.pop().sequence_id == 2
    assert buf.pop().sequence_id == 3
    assert buf.is_empty is True


def test_buffer_overflow_drop_newest():
    buf = BoundedAudioBuffer(capacity=3, overflow_strategy=OverflowStrategy.DROP_NEWEST)
    for i in range(3):
        buf.push(make_chunk(i))

    c3 = make_chunk(3)
    pushed = buf.push(c3)
    assert pushed is False
    assert buf.size == 3  # Buffer remains strictly bounded!
    assert buf.dropped_chunks == 1

    # Remaining chunks should still be 0, 1, 2
    assert buf.pop().sequence_id == 0
    assert buf.pop().sequence_id == 1
    assert buf.pop().sequence_id == 2
    assert buf.is_empty is True


def test_buffer_overflow_reject():
    buf = BoundedAudioBuffer(capacity=2, overflow_strategy=OverflowStrategy.REJECT)
    buf.push(make_chunk(0))
    buf.push(make_chunk(1))

    with pytest.raises(AudioError) as exc:
        buf.push(make_chunk(2))
    assert exc.value.code == AudioErrorCode.BUFFER_OVERFLOW
    assert buf.dropped_chunks == 1
    assert buf.size == 2


def test_buffer_release_and_cleanup():
    buf = BoundedAudioBuffer(capacity=10)
    for i in range(5):
        buf.push(make_chunk(i))
    assert buf.size == 5

    buf.release()
    assert buf.size == 0
    assert buf.is_empty is True
    assert buf.pop() is None
