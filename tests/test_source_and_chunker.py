import pytest

from academia_audio import (
    AudioError,
    AudioErrorCode,
    AudioFormat,
    MockMicrophone,
    assert_stream_order,
    chunk_pcm,
)

FMT = AudioFormat(16000, 1)


def test_mock_source_is_deterministic():
    run1 = list(MockMicrophone(duration_s=1.0))
    run2 = list(MockMicrophone(duration_s=1.0))
    assert run1 == run2  # dataclass equality: ids, timestamps, format, bytes, checksum


def test_chunk_count_and_size():
    chunks = list(MockMicrophone(FMT, duration_s=1.0, chunk_ms=20))
    assert len(chunks) == 50
    assert all(c.size_bytes == 640 for c in chunks)  # 320 frames * 2 bytes


def test_sequence_and_timestamps_strictly_increase():
    chunks = list(MockMicrophone(duration_s=1.0))
    assert [c.sequence_id for c in chunks] == list(range(len(chunks)))
    assert assert_stream_order(chunks) == len(chunks)
    assert chunks[0].timestamp_s == 0.0
    assert chunks[1].timestamp_s == pytest.approx(0.02)


def test_stereo_output():
    chunks = list(MockMicrophone(AudioFormat(48000, 2), duration_s=0.1, chunk_ms=10))
    assert all(c.size_bytes == 480 * 4 for c in chunks)


def test_audio_has_silence_and_tone():
    pcm = MockMicrophone(duration_s=1.0, segment_s=0.5).generate_pcm()
    half = len(pcm) // 2
    assert set(pcm[:half]) == {0}  # first segment: silence
    assert any(pcm[half:])  # second segment: tone


def test_last_chunk_may_be_shorter():
    pcm = b"\x00\x00" * 500
    chunks = list(chunk_pcm(pcm, FMT, chunk_ms=20))  # 320 + 180 frames
    assert [c.num_frames for c in chunks] == [320, 180]
    assert chunks[1].timestamp_s == pytest.approx(320 / 16000)


def test_start_sequence_id():
    chunks = list(chunk_pcm(b"\x00\x00" * 640, FMT, 20, start_sequence_id=10))
    assert [c.sequence_id for c in chunks] == [10, 11]


# ---- bad input -----------------------------------------------------------
def test_chunker_rejects_empty():
    with pytest.raises(AudioError) as e:
        chunk_pcm(b"", FMT)
    assert e.value.code == AudioErrorCode.EMPTY_CHUNK


def test_chunker_rejects_corrupt_length():
    with pytest.raises(AudioError) as e:
        chunk_pcm(b"\x00" * 7, FMT)
    assert e.value.code == AudioErrorCode.CORRUPT_CHUNK


def test_chunker_rejects_non_bytes():
    with pytest.raises(AudioError) as e:
        chunk_pcm("abc", FMT)  # type: ignore[arg-type]
    assert e.value.code == AudioErrorCode.INVALID_DATA_TYPE


@pytest.mark.parametrize("chunk_ms", [0, -5, 1.5, "20"])
def test_chunker_rejects_bad_chunk_ms(chunk_ms):
    with pytest.raises(AudioError) as e:
        chunk_pcm(b"\x00\x00" * 320, FMT, chunk_ms)
    assert e.value.code == AudioErrorCode.INVALID_PARAMETER


def test_chunk_ms_must_be_whole_frames():
    with pytest.raises(AudioError):
        chunk_pcm(b"\x00\x00" * 1000, AudioFormat(22050, 1), chunk_ms=10)  # 220.5 frames


@pytest.mark.parametrize(
    "kwargs",
    [
        {"duration_s": 0},
        {"duration_s": -1},
        {"duration_s": 10_000},
        {"frequency_hz": 0},
        {"frequency_hz": 9000},  # above Nyquist for 16 kHz
        {"amplitude": 0},
        {"amplitude": 1.5},
        {"segment_s": 0},
    ],
)
def test_mock_source_rejects_bad_params(kwargs):
    with pytest.raises(AudioError) as e:
        MockMicrophone(**kwargs)
    assert e.value.code == AudioErrorCode.INVALID_PARAMETER
