"""
SDE 4 - Speech-to-Text (W3) Core Library
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
# W3 additions
from sde4_stt.session import CancellationToken, SessionContext, SessionManager
from sde4_stt.fallback import FallbackAdapter
from sde4_stt.event_bridge import EventBridgePublisher, make_no_op_publisher
from sde4_stt.workflow_bridge import VoiceWorkflowBridge

__version__ = "0.3.0"

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
    # W3: Session management
    "CancellationToken",
    "SessionContext",
    "SessionManager",
    # W3: Fallback adapter
    "FallbackAdapter",
    # W3: Event bridge
    "EventBridgePublisher",
    "make_no_op_publisher",
    # W3: Workflow bridge
    "VoiceWorkflowBridge",
]

