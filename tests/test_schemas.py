import pytest

from academia_audio import AudioChunk, AudioError, AudioErrorCode, AudioFormat, assert_stream_order
from academia_audio.schemas import crc32

FMT = AudioFormat(16000, 1)


def code_of(exc_info) -> AudioErrorCode:
    return exc_info.value.code


# ---- happy path ----------------------------------------------------------
def test_valid_format_and_chunk():
    data = b"\x01\x00" * 320
    chunk = AudioChunk(0, 0.0, FMT, data, checksum=crc32(data))
    assert chunk.size_bytes == 640
    assert chunk.num_frames == 320
    assert chunk.duration_s == pytest.approx(0.02)
    assert str(FMT) == "16000Hz/1ch/pcm_s16le"
    assert AudioFormat(48000, 2).frame_size == 4


# ---- invalid format ------------------------------------------------------
@pytest.mark.parametrize("rate", [0, -16000, 12345, 16000.0, "16000", None, True])
def test_invalid_sample_rate(rate):
    with pytest.raises(AudioError) as e:
        AudioFormat(rate, 1)
    assert code_of(e) == AudioErrorCode.INVALID_SAMPLE_RATE
    assert "sample_rate" in str(e.value)


@pytest.mark.parametrize("channels", [0, 3, -1, 1.5, "2", None, True])
def test_invalid_channels(channels):
    with pytest.raises(AudioError) as e:
        AudioFormat(16000, channels)
    assert code_of(e) == AudioErrorCode.INVALID_CHANNELS


def test_invalid_sample_width():
    with pytest.raises(AudioError) as e:
        AudioFormat(16000, 1, sample_width=4)
    assert code_of(e) == AudioErrorCode.INVALID_SAMPLE_WIDTH


# ---- empty chunk ---------------------------------------------------------
def test_empty_chunk():
    with pytest.raises(AudioError) as e:
        AudioChunk(0, 0.0, FMT, b"")
    assert code_of(e) == AudioErrorCode.EMPTY_CHUNK


# ---- corrupt chunk -------------------------------------------------------
def test_misaligned_data_is_corrupt():
    with pytest.raises(AudioError) as e:
        AudioChunk(0, 0.0, FMT, b"\x00" * 3)  # 3 bytes: not whole 16-bit frames
    assert code_of(e) == AudioErrorCode.CORRUPT_CHUNK


def test_stereo_requires_whole_frames():
    with pytest.raises(AudioError) as e:
        AudioChunk(0, 0.0, AudioFormat(16000, 2), b"\x00" * 6)  # frame = 4 bytes
    assert code_of(e) == AudioErrorCode.CORRUPT_CHUNK


def test_checksum_mismatch_is_corrupt():
    good = b"\x01\x00" * 10
    with pytest.raises(AudioError) as e:
        AudioChunk(0, 0.0, FMT, good, checksum=crc32(good) ^ 1)
    assert code_of(e) == AudioErrorCode.CORRUPT_CHUNK
    assert "checksum" in str(e.value)


def test_flipped_byte_detected():
    good = b"\x01\x00" * 10
    bad = b"\xff" + good[1:]
    with pytest.raises(AudioError):
        AudioChunk(0, 0.0, FMT, bad, checksum=crc32(good))


@pytest.mark.parametrize("data", ["text", None, bytearray(b"\x00\x00"), [0, 0]])
def test_wrong_data_type(data):
    with pytest.raises(AudioError) as e:
        AudioChunk(0, 0.0, FMT, data)
    assert code_of(e) == AudioErrorCode.INVALID_DATA_TYPE


# ---- bad metadata --------------------------------------------------------
@pytest.mark.parametrize("seq", [-1, 1.0, "0", None, True])
def test_invalid_sequence_id(seq):
    with pytest.raises(AudioError) as e:
        AudioChunk(seq, 0.0, FMT, b"\x00\x00")
    assert code_of(e) == AudioErrorCode.INVALID_SEQUENCE_ID


@pytest.mark.parametrize("ts", [-0.1, float("nan"), float("inf"), "0", None, True])
def test_invalid_timestamp(ts):
    with pytest.raises(AudioError) as e:
        AudioChunk(0, ts, FMT, b"\x00\x00")
    assert code_of(e) == AudioErrorCode.INVALID_TIMESTAMP


def test_format_must_be_audioformat():
    with pytest.raises(AudioError) as e:
        AudioChunk(0, 0.0, "16k", b"\x00\x00")
    assert code_of(e) == AudioErrorCode.INVALID_FORMAT


def test_chunks_are_immutable():
    chunk = AudioChunk(0, 0.0, FMT, b"\x00\x00")
    with pytest.raises(Exception):
        chunk.sequence_id = 5  # type: ignore[misc]


# ---- ordering ------------------------------------------------------------
def test_stream_order_ok_and_violations():
    a = AudioChunk(0, 0.0, FMT, b"\x00\x00")
    b = AudioChunk(1, 0.02, FMT, b"\x00\x00")
    assert assert_stream_order([a, b]) == 2
    with pytest.raises(AudioError) as e:
        assert_stream_order([b, a])
    assert code_of(e) == AudioErrorCode.OUT_OF_ORDER
    with pytest.raises(AudioError):
        assert_stream_order([a, a])
