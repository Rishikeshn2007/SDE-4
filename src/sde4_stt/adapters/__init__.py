"""Speech-to-text adapters export.

Default adapter is FakeTranscriber (zero-cost, deterministic, offline).
RealSpeechTranscriber is optional and loaded lazily on demand.
"""

from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.adapters.fake_transcriber import FakeTranscriber

__all__ = [
    "BaseTranscriberAdapter",
    "FakeTranscriber",
]


def __getattr__(name: str):
    if name == "RealSpeechTranscriber":
        from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber
        return RealSpeechTranscriber
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
