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
    PERMISSION_DENIED = "permission_denied"
    DEVICE_UNSUPPORTED = "device_unsupported"
    DEVICE_NOT_FOUND = "device_not_found"
    ILLEGAL_STATE_TRANSITION = "illegal_state_transition"
    BUFFER_OVERFLOW = "buffer_overflow"
    AUDIO_GAP_DETECTED = "audio_gap_detected"
    DEVICE_LOST = "device_lost"
    SESSION_CANCELLED = "session_cancelled"
    INVALID_EVENT = "invalid_event"
    RECONNECTION_FAILED = "reconnection_failed"


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


# --------------------------------------------------------------------------
# Week 3: Speech & Audio Pipeline Events
# --------------------------------------------------------------------------
def _validate_id(name: str, value: object) -> str:
    """Validate that session_id or correlation_id is a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise AudioError(
            AudioErrorCode.INVALID_PARAMETER,
            f"{name} must be a non-empty string, got {value!r}",
        )
    return value.strip()


class AudioEventType(str, Enum):
    """Categorical type indicator for events emitted by the audio pipeline."""

    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    AUDIO_CHUNK = "audio_chunk"
    DEVICE_DISCONNECTED = "device_disconnected"
    DEVICE_RECONNECTED = "device_reconnected"
    SESSION_CANCELLED = "session_cancelled"


@dataclass(frozen=True)
class BaseAudioEvent:
    """Base event contract for all events emitted by the audio pipeline.

    Every event carries strict session and correlation tracking IDs.

    Fields:
        event_id:       Unique identifier for the event (e.g. 'evt_sess1_0').
        session_id:     Identifier of the active interaction session.
        correlation_id: Distributed tracing correlation identifier.
        event_type:     :class:`AudioEventType` indicating the event category.
        timestamp_s:    Timestamp in seconds relative to session start (>= 0.0).
        sequence_id:    Monotonically increasing event sequence counter (>= 0).
    """

    event_id: str
    session_id: str
    correlation_id: str
    event_type: AudioEventType
    timestamp_s: float
    sequence_id: int

    def __post_init__(self) -> None:
        _validate_id("event_id", self.event_id)
        _validate_id("session_id", self.session_id)
        _validate_id("correlation_id", self.correlation_id)
        if not isinstance(self.event_type, AudioEventType):
            raise AudioError(
                AudioErrorCode.INVALID_PARAMETER,
                f"event_type must be an AudioEventType, got {self.event_type!r}",
            )
        if (
            isinstance(self.timestamp_s, bool)
            or not isinstance(self.timestamp_s, (int, float))
            or not math.isfinite(self.timestamp_s)
            or self.timestamp_s < 0.0
        ):
            raise AudioError(
                AudioErrorCode.INVALID_TIMESTAMP,
                f"timestamp_s must be a finite float >= 0.0, got {self.timestamp_s!r}",
            )
        if not _is_int(self.sequence_id) or self.sequence_id < 0:
            raise AudioError(
                AudioErrorCode.INVALID_SEQUENCE_ID,
                f"sequence_id must be an int >= 0, got {self.sequence_id!r}",
            )


@dataclass(frozen=True)
class SpeechStartEvent(BaseAudioEvent):
    """Emitted when Voice Activity Detection transitions from silence to speech.

    Guaranteed to precede any speech-bearing audio chunks within an utterance.

    Fields:
        speech_start_time_s: Audio timestamp where speech onset was detected.
    """

    speech_start_time_s: float = 0.0

    def __post_init__(self) -> None:
        super().__post_init__()
        if (
            isinstance(self.speech_start_time_s, bool)
            or not isinstance(self.speech_start_time_s, (int, float))
            or not math.isfinite(self.speech_start_time_s)
            or self.speech_start_time_s < 0.0
        ):
            raise AudioError(
                AudioErrorCode.INVALID_TIMESTAMP,
                f"speech_start_time_s must be a finite float >= 0.0, got {self.speech_start_time_s!r}",
            )


@dataclass(frozen=True)
class SpeechEndEvent(BaseAudioEvent):
    """Emitted when Voice Activity Detection transitions from speech back to silence.

    Guaranteed to conclude an utterance following a preceding :class:`SpeechStartEvent`.

    Fields:
        speech_start_time_s: Audio timestamp where speech began.
        speech_end_time_s:   Audio timestamp where speech concluded.
        duration_s:          Total speech duration in seconds.
    """

    speech_start_time_s: float = 0.0
    speech_end_time_s: float = 0.0
    duration_s: float = 0.0

    def __post_init__(self) -> None:
        super().__post_init__()
        if (
            isinstance(self.speech_start_time_s, bool)
            or not isinstance(self.speech_start_time_s, (int, float))
            or not math.isfinite(self.speech_start_time_s)
            or self.speech_start_time_s < 0.0
        ):
            raise AudioError(
                AudioErrorCode.INVALID_TIMESTAMP,
                f"speech_start_time_s must be a finite float >= 0.0, got {self.speech_start_time_s!r}",
            )
        if (
            isinstance(self.speech_end_time_s, bool)
            or not isinstance(self.speech_end_time_s, (int, float))
            or not math.isfinite(self.speech_end_time_s)
            or self.speech_end_time_s < self.speech_start_time_s
        ):
            raise AudioError(
                AudioErrorCode.INVALID_TIMESTAMP,
                f"speech_end_time_s must be >= speech_start_time_s, got {self.speech_end_time_s!r}",
            )
        if (
            isinstance(self.duration_s, bool)
            or not isinstance(self.duration_s, (int, float))
            or not math.isfinite(self.duration_s)
            or self.duration_s < 0.0
        ):
            raise AudioError(
                AudioErrorCode.INVALID_PARAMETER,
                f"duration_s must be a finite float >= 0.0, got {self.duration_s!r}",
            )


@dataclass(frozen=True)
class AudioChunkEvent(BaseAudioEvent):
    """Normalized audio payload emitted for every captured chunk in the pipeline.

    Fields:
        chunk:      The underlying normalized :class:`AudioChunk`.
        is_speech:  True if VAD classified this chunk as active voice activity.
        rms_energy: Normalized acoustic RMS power [0.0, 1.0].
    """

    chunk: AudioChunk = None  # type: ignore
    is_speech: bool = False
    rms_energy: float = 0.0

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.chunk, AudioChunk):
            raise AudioError(
                AudioErrorCode.INVALID_DATA_TYPE,
                f"chunk must be an AudioChunk instance, got {type(self.chunk).__name__}",
            )
        if not isinstance(self.is_speech, bool):
            raise AudioError(
                AudioErrorCode.INVALID_PARAMETER,
                f"is_speech must be a bool, got {type(self.is_speech).__name__}",
            )
        if (
            isinstance(self.rms_energy, bool)
            or not isinstance(self.rms_energy, (int, float))
            or not (0.0 <= self.rms_energy <= 1.0)
        ):
            raise AudioError(
                AudioErrorCode.INVALID_PARAMETER,
                f"rms_energy must be in [0.0, 1.0], got {self.rms_energy!r}",
            )


@dataclass(frozen=True)
class DeviceDisconnectedEvent(BaseAudioEvent):
    """Emitted when an active audio input device disconnection is detected.

    Fields:
        device_id: ID of the disconnected device.
        reason:    Descriptive reason or error message for disconnection.
    """

    device_id: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _validate_id("device_id", self.device_id)


@dataclass(frozen=True)
class DeviceReconnectedEvent(BaseAudioEvent):
    """Emitted when audio input device reconnection succeeds without crashing.

    Fields:
        device_id:          ID of the reconnected or newly selected device.
        reconnect_attempts: Number of reconnection attempts made before success.
    """

    device_id: str = ""
    reconnect_attempts: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        _validate_id("device_id", self.device_id)
        if not _is_int(self.reconnect_attempts) or self.reconnect_attempts < 1:
            raise AudioError(
                AudioErrorCode.INVALID_PARAMETER,
                f"reconnect_attempts must be an int >= 1, got {self.reconnect_attempts!r}",
            )


@dataclass(frozen=True)
class SessionCancelledEvent(BaseAudioEvent):
    """Emitted when an active capture session is cancelled by user or caller.

    Fields:
        reason: Explanation for session cancellation.
    """

    reason: str = ""

