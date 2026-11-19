"""Transcript schemas and re-export of authoritative W1 audio contracts."""

from academia_audio.schemas import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
)
from sde4_stt.schemas.transcript import (
    TranscriptError,
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
    WordTiming,
)

__all__ = [
    "AudioChunk",
    "AudioFormat",
    "AudioError",
    "AudioErrorCode",
    "TranscriptEventType",
    "WordTiming",
    "TranscriptSegment",
    "TranscriptError",
    "TranscriptEvent",
]
