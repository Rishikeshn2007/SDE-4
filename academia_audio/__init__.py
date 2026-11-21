"""Academia AI Voice Bot - Audio & VAD (Weeks 1, 2, and 3 Foundation)."""

from .buffer import BoundedAudioBuffer, OverflowStrategy
from .chunker import chunk_pcm, frames_per_chunk
from .device import (
    DEFAULT_MOCK_DEVICES,
    DeviceAdapter,
    DeviceInfo,
    MockDeviceAdapter,
    PermissionState,
)
from .lifecycle import AudioPipeline, LifecycleState
from .mock_source import MockMicrophone
from .normalization import (
    compute_peak_amplitude,
    normalize_audio_chunk,
    normalize_pcm_bytes,
)
from .schemas import (
    ENCODING,
    SAMPLE_WIDTH_BYTES,
    SUPPORTED_CHANNELS,
    SUPPORTED_SAMPLE_RATES,
    AudioChunk,
    AudioChunkEvent,
    AudioError,
    AudioErrorCode,
    AudioEventType,
    AudioFormat,
    BaseAudioEvent,
    DeviceDisconnectedEvent,
    DeviceReconnectedEvent,
    SessionCancelledEvent,
    SpeechEndEvent,
    SpeechStartEvent,
    _validate_id,
    assert_stream_order,
    crc32,
)
from .transcription import (
    MockTranscriptEvent,
    MockTranscriptEventType,
    MockTranscriptSegment,
    MockTranscriptionAdapter,
    MockWordTiming,
    TranscriptionBridge,
)
from .vad import BaseVAD, MockVAD, VADResult, compute_rms

__all__ = [
    # Schemas (W1)
    "AudioChunk",
    "AudioError",
    "AudioErrorCode",
    "AudioFormat",
    "ENCODING",
    "SAMPLE_WIDTH_BYTES",
    "SUPPORTED_CHANNELS",
    "SUPPORTED_SAMPLE_RATES",
    "assert_stream_order",
    "crc32",
    # Source & Chunker (W1)
    "MockMicrophone",
    "chunk_pcm",
    "frames_per_chunk",
    # Device Adapter (W2)
    "DEFAULT_MOCK_DEVICES",
    "DeviceAdapter",
    "DeviceInfo",
    "MockDeviceAdapter",
    "PermissionState",
    # Bounded Buffer (W2)
    "BoundedAudioBuffer",
    "OverflowStrategy",
    # Voice Activity Detection (W2)
    "BaseVAD",
    "MockVAD",
    "VADResult",
    "compute_rms",
    # Lifecycle & Pipeline (W2)
    "AudioPipeline",
    "LifecycleState",
    # Speech Events & Schemas (W3)
    "AudioEventType",
    "BaseAudioEvent",
    "SpeechStartEvent",
    "SpeechEndEvent",
    "AudioChunkEvent",
    "DeviceDisconnectedEvent",
    "DeviceReconnectedEvent",
    "SessionCancelledEvent",
    "_validate_id",
    # Normalization (W3)
    "compute_peak_amplitude",
    "normalize_pcm_bytes",
    "normalize_audio_chunk",
    # Transcription Integration (W3)
    "MockTranscriptEventType",
    "MockWordTiming",
    "MockTranscriptSegment",
    "MockTranscriptEvent",
    "MockTranscriptionAdapter",
    "TranscriptionBridge",
]
