"""Academia AI Voice Bot - Audio & VAD (Week 1 & Week 2 Foundation)."""

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
from .schemas import (
    ENCODING,
    SAMPLE_WIDTH_BYTES,
    SUPPORTED_CHANNELS,
    SUPPORTED_SAMPLE_RATES,
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
    assert_stream_order,
    crc32,
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
]
