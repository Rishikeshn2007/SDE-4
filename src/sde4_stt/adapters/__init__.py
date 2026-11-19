"""Speech-to-text adapters export.

Exports:
- BaseTranscriberAdapter: Provider-neutral abstract base interface
- FakeTranscriber: Deterministic, zero-cost, offline mock transcriber

Note:
RealSpeechTranscriber is an optional real provider adapter requiring the optional
dependency SpeechRecognition. It is intentionally NOT exported here to prevent
eagerly importing or requiring optional dependencies during normal package initialization.
Import it directly from its own module when needed:
    from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber
"""

from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.adapters.fake_transcriber import FakeTranscriber

__all__ = [
    "BaseTranscriberAdapter",
    "FakeTranscriber",
]
