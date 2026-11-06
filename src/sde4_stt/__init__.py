"""
SDE 4 - Speech-to-Text (W2) Core Library
Academia AI Voice Co-Pilot Project
"""

from academia_audio.schemas import AudioChunk, AudioFormat, AudioError, AudioErrorCode
from sde4_stt.schemas.transcript import (
    TranscriptEventType,
    WordTiming,
    TranscriptSegment,
    TranscriptError,
    TranscriptEvent,
)
from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.accumulator import SegmentAccumulator
from sde4_stt.dedup import EventDeduplicator
from sde4_stt.preprocessing import AudioPreprocessor
from sde4_stt.retry import NormalizedError, RetryableAdapter, RetryConfig
from sde4_stt.orchestrator import TranscriptionOrchestrator, TranscriptionResult
from sde4_stt.vad import VADConfig, VADResult, VADState, VoiceActivityDetector

__version__ = "0.2.0"

__all__ = [
    # Schemas (authoritative W1 audio + W2 transcript)
    "AudioChunk",
    "AudioFormat",
    "AudioError",
    "AudioErrorCode",
    "TranscriptEventType",
    "WordTiming",
    "TranscriptSegment",
    "TranscriptError",
    "TranscriptEvent",
    # Adapters (FakeTranscriber default, RealSpeechTranscriber imported directly from real_transcriber)
    "BaseTranscriberAdapter",
    "FakeTranscriber",
    # Accumulation & Dedup
    "SegmentAccumulator",
    "EventDeduplicator",
    # Preprocessing & VAD
    "AudioPreprocessor",
    "VADConfig",
    "VADResult",
    "VADState",
    "VoiceActivityDetector",
    # Resiliency
    "RetryConfig",
    "NormalizedError",
    "RetryableAdapter",
    # Orchestration
    "TranscriptionOrchestrator",
    "TranscriptionResult",
]
