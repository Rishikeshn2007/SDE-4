"""Speech-to-text adapters export."""

from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber

__all__ = [
    "BaseTranscriberAdapter",
    "FakeTranscriber",
    "RealSpeechTranscriber",
]

