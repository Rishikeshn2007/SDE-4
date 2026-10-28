"""Audio contracts for the Academia AI Voice Bot (W1 - Audio & VAD).

This is the SINGLE place where ``AudioFormat``, ``AudioChunk`` and
``AudioError`` are defined. Other modules (and other workstreams, e.g. W2)
must import them from here and never redefine them.

Conventions
-----------
* Audio is raw, interleaved, little-endian signed 16-bit PCM (``pcm_s16le``).
* Time is expressed in seconds, relative to the start of the stream (0.0).
* All schemas are immutable (frozen dataclasses) and validated on creation:
  an invalid object can never exist.
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

# --------------------------------------------------------------------------
# Constants (the contract limits - change only with a team decision)
# --------------------------------------------------------------------------
SUPPORTED_SAMPLE_RATES = (8000, 16000, 22050, 24000, 32000, 44100, 48000)  # Hz
SUPPORTED_CHANNELS = (1, 2)  # mono, stereo
SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM
ENCODING = "pcm_s16le"


# --------------------------------------------------------------------------
# AudioError
# --------------------------------------------------------------------------
class AudioErrorCode(str, Enum):
    """Machine-readable reason carried by every :class:`AudioError`."""

    INVALID_SAMPLE_RATE = "invalid_sample_rate"
    INVALID_CHANNELS = "invalid_channels"
    INVALID_SAMPLE_WIDTH = "invalid_sample_width"
    INVALID_FORMAT = "invalid_format"
    INVALID_SEQUENCE_ID = "invalid_sequence_id"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_DATA_TYPE = "invalid_data_type"
    INVALID_PARAMETER = "invalid_parameter"
    EMPTY_CHUNK = "empty_chunk"
    CORRUPT_CHUNK = "corrupt_chunk"
    OUT_OF_ORDER = "out_of_order"


class AudioError(Exception):
    """Raised for any invalid audio input in the W1 pipeline.

    Attributes:
        code:    :class:`AudioErrorCode` - stable, machine-readable reason.
        message: Human-readable explanation (also the ``str()`` of the error).
    """

    def __init__(self, code: AudioErrorCode, message: str) -> None:
        super().__init__(f"[{code.value}] {message}")
        self.code = code
        self.message = message


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _is_int(value: object) -> bool:
    # bool is a subclass of int in Python; True/False are not valid numbers here.
    return isinstance(value, int) and not isinstance(value, bool)


def crc32(data: bytes) -> int:
    """CRC-32 of ``data`` as an unsigned 32-bit int (used for corruption checks)."""
    return zlib.crc32(data) & 0xFFFFFFFF


# --------------------------------------------------------------------------
# AudioFormat
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AudioFormat:
    """Describes how raw PCM bytes must be interpreted.

    Fields:
        sample_rate:  int, Hz. One of ``SUPPORTED_SAMPLE_RATES``.
        channels:     int, count. 1 (mono) or 2 (stereo).
        sample_width: int, bytes per sample per channel. Must be 2 (16-bit PCM).

    Raises:
        AudioError: INVALID_SAMPLE_RATE, INVALID_CHANNELS or INVALID_SAMPLE_WIDTH.
    """

    sample_rate: int
    channels: int
    sample_width: int = SAMPLE_WIDTH_BYTES

    def __post_init__(self) -> None:
        if not _is_int(self.sample_rate) or self.sample_rate not in SUPPORTED_SAMPLE_RATES:
            raise AudioError(
                AudioErrorCode.INVALID_SAMPLE_RATE,
                f"sample_rate must be one of {list(SUPPORTED_SAMPLE_RATES)} Hz, "
                f"got {self.sample_rate!r}",
            )
        if not _is_int(self.channels) or self.channels not in SUPPORTED_CHANNELS:
            raise AudioError(
                AudioErrorCode.INVALID_CHANNELS,
                f"channels must be one of {list(SUPPORTED_CHANNELS)}, got {self.channels!r}",
            )
        if not _is_int(self.sample_width) or self.sample_width != SAMPLE_WIDTH_BYTES:
            raise AudioError(
                AudioErrorCode.INVALID_SAMPLE_WIDTH,
                f"sample_width must be {SAMPLE_WIDTH_BYTES} bytes (16-bit PCM), "
                f"got {self.sample_width!r}",
            )

    @property
    def frame_size(self) -> int:
        """Bytes in one frame (one sample for every channel)."""
        return self.channels * self.sample_width

    @property
    def bytes_per_second(self) -> int:
        return self.sample_rate * self.frame_size

    def __str__(self) -> str:
        return f"{self.sample_rate}Hz/{self.channels}ch/{ENCODING}"


# --------------------------------------------------------------------------
# AudioChunk
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AudioChunk:
    """A short, ordered slice of an audio stream.

    Fields:
        sequence_id: int, >= 0. Position in the stream; strictly increasing.
        timestamp_s: float, seconds, >= 0, finite. Start time of the chunk
                     relative to stream start.
        format:      :class:`AudioFormat` of ``data``.
        data:        bytes, non-empty. Raw PCM; length must be a whole number
                     of frames (``format.frame_size``).
        checksum:    optional int. CRC-32 of ``data``; when given it is verified
                     so corrupted payloads are rejected.

    Raises:
        AudioError: see :class:`AudioErrorCode` (EMPTY_CHUNK, CORRUPT_CHUNK, ...).
    """

    sequence_id: int
    timestamp_s: float
    format: AudioFormat
    data: bytes
    checksum: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.format, AudioFormat):
            raise AudioError(
                AudioErrorCode.INVALID_FORMAT,
                f"format must be an AudioFormat, got {type(self.format).__name__}",
            )
        if not _is_int(self.sequence_id) or self.sequence_id < 0:
            raise AudioError(
                AudioErrorCode.INVALID_SEQUENCE_ID,
                f"sequence_id must be an int >= 0, got {self.sequence_id!r}",
            )
        if (
            isinstance(self.timestamp_s, bool)
            or not isinstance(self.timestamp_s, (int, float))
            or not math.isfinite(self.timestamp_s)
            or self.timestamp_s < 0
        ):
            raise AudioError(
                AudioErrorCode.INVALID_TIMESTAMP,
                f"timestamp_s must be a finite number >= 0 (seconds), got {self.timestamp_s!r}",
            )
        if not isinstance(self.data, bytes):
            raise AudioError(
                AudioErrorCode.INVALID_DATA_TYPE,
                f"data must be bytes, got {type(self.data).__name__}",
            )
        if len(self.data) == 0:
            raise AudioError(AudioErrorCode.EMPTY_CHUNK, "chunk data is empty")
        if len(self.data) % self.format.frame_size != 0:
            raise AudioError(
                AudioErrorCode.CORRUPT_CHUNK,
                f"data length {len(self.data)} is not a multiple of the frame size "
                f"{self.format.frame_size} ({self.format})",
            )
        if self.checksum is not None:
            if not _is_int(self.checksum):
                raise AudioError(
                    AudioErrorCode.CORRUPT_CHUNK, f"checksum must be an int, got {self.checksum!r}"
                )
            actual = crc32(self.data)
            if actual != self.checksum:
                raise AudioError(
                    AudioErrorCode.CORRUPT_CHUNK,
                    f"checksum mismatch: expected {self.checksum:#010x}, got {actual:#010x}",
                )

    @property
    def size_bytes(self) -> int:
        return len(self.data)

    @property
    def num_frames(self) -> int:
        return len(self.data) // self.format.frame_size

    @property
    def duration_s(self) -> float:
        return self.num_frames / self.format.sample_rate


# --------------------------------------------------------------------------
# stream-level validation
# --------------------------------------------------------------------------
def assert_stream_order(chunks: Iterable[AudioChunk]) -> int:
    """Check sequence IDs and timestamps are strictly increasing.

    Returns the number of chunks checked.

    Raises:
        AudioError: OUT_OF_ORDER if a chunk's sequence_id or timestamp does not
                    strictly increase over the previous chunk.
    """
    prev: Optional[AudioChunk] = None
    count = 0
    for chunk in chunks:
        if prev is not None:
            if chunk.sequence_id <= prev.sequence_id:
                raise AudioError(
                    AudioErrorCode.OUT_OF_ORDER,
                    f"sequence_id {chunk.sequence_id} does not follow {prev.sequence_id}",
                )
            if chunk.timestamp_s <= prev.timestamp_s:
                raise AudioError(
                    AudioErrorCode.OUT_OF_ORDER,
                    f"timestamp {chunk.timestamp_s} does not follow {prev.timestamp_s}",
                )
        prev = chunk
        count += 1
    return count
