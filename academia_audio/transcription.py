"""Transcription integration and mock transcriber adapter (Week 3 - Audio & VAD).

Connects AudioPipeline speech events to the team's speech-to-text pipeline.
Inspects the team's Transcriber Adapter contract (BaseTranscriberAdapter) and
provides a clearly identified mock adapter for testability and offline execution
when the external transcription package (sde4_stt) is unavailable in the environment.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Iterator, List, Optional, Union

from .schemas import (
    AudioChunk,
    AudioChunkEvent,
    AudioError,
    AudioErrorCode,
    AudioEventType,
    BaseAudioEvent,
    SessionCancelledEvent,
    SpeechEndEvent,
    SpeechStartEvent,
)

# --------------------------------------------------------------------------
# Mock STT Event Schemas (Matches sde4_stt contract without duplicating files)
# --------------------------------------------------------------------------
class MockTranscriptEventType(str, Enum):
    """Event types emitted during speech transcription."""

    START = "start"
    INTERIM = "interim"
    FINAL = "final"
    ERROR = "error"
    COMPLETE = "complete"


@dataclass(frozen=True)
class MockWordTiming:
    """Individual word timing and confidence within a transcript segment."""

    word: str
    start_time: float
    end_time: float
    confidence: float = 0.95


@dataclass(frozen=True)
class MockTranscriptSegment:
    """Recognized speech segment carrying transcription text and word timings."""

    segment_id: str
    sequence_number: int
    text: str
    start_time: float
    end_time: float
    is_final: bool
    confidence: float = 0.95
    language: str = "en"
    words: Optional[List[MockWordTiming]] = None


@dataclass(frozen=True)
class MockTranscriptEvent:
    """Event emitted by the speech-to-text pipeline."""

    event_id: str
    session_id: str
    event_type: MockTranscriptEventType
    timestamp: float
    segment: Optional[MockTranscriptSegment] = None
    error: Optional[Any] = None


# Default mock vocabulary for deterministic speech-to-text token mapping
DEFAULT_MOCK_VOCABULARY = [
    "academia", "voice", "assistant", "speech", "pipeline",
    "event", "audio", "chunk", "recognition", "active",
]


# --------------------------------------------------------------------------
# MockTranscriptionAdapter
# Clearly identified mock adapter for testing without pretending real integration is complete.
# --------------------------------------------------------------------------
class MockTranscriptionAdapter:
    """Clearly identified Mock Speech-to-Text Transcriber Adapter.

    NOTE: This is a clearly identified mock adapter used when the external STT
    module (sde4_stt) is unavailable in the local environment. It conforms
    to the team's BaseTranscriberAdapter interface for end-to-end testing.
    """

    is_mock_adapter: bool = True

    def __init__(
        self,
        canned_transcript: Optional[str] = "academia voice assistant speech pipeline active",
        fixed_confidence: float = 0.95,
    ) -> None:
        self.provider_name: str = "clearly-identified-mock-transcriber"
        self._canned_transcript: Optional[str] = canned_transcript
        self._canned_words: List[str] = canned_transcript.split() if canned_transcript else []
        self._fixed_confidence: float = fixed_confidence
        self._session_id: Optional[str] = None
        self._is_active: bool = False
        self._chunk_count: int = 0
        self._accumulated_words: List[str] = []
        self._has_emitted_final: bool = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    def start_session(
        self,
        session_id: str,
        language: str = "en",
        sample_rate: int = 16000,
    ) -> List[MockTranscriptEvent]:
        """Initializes a transcription session."""
        if not session_id or not session_id.strip():
            raise ValueError("session_id must be non-empty")
        self._session_id = session_id.strip()
        self._is_active = True
        self._chunk_count = 0
        self._accumulated_words = []
        self._has_emitted_final = False

        start_event = MockTranscriptEvent(
            event_id=f"evt_stt_{self._session_id}_start",
            session_id=self._session_id,
            event_type=MockTranscriptEventType.START,
            timestamp=0.0,
        )
        return [start_event]

    def process_chunk(
        self,
        chunk: Union[AudioChunk, bytes],
    ) -> List[MockTranscriptEvent]:
        """Processes an audio chunk and deterministically produces transcript events."""
        if not self._is_active or self._session_id is None:
            raise RuntimeError("Cannot process chunks without an active session. Call start_session() first.")

        # Extract sequence and timestamp if available
        if isinstance(chunk, AudioChunk):
            seq = chunk.sequence_id
            ts = chunk.timestamp_s
            data = chunk.data
        elif hasattr(chunk, "data"):
            data = bytes(chunk.data)
            seq = getattr(chunk, "sequence_id", self._chunk_count)
            ts = getattr(chunk, "timestamp_s", 0.0)
        else:
            data = bytes(chunk)
            seq = self._chunk_count
            ts = 0.0

        self._chunk_count += 1

        # Pick words deterministically from canned transcript or chunk data hash
        if self._canned_words:
            word_idx = seq % len(self._canned_words)
            word = self._canned_words[word_idx]
        else:
            h = hashlib.sha256(data).digest()
            word = DEFAULT_MOCK_VOCABULARY[h[0] % len(DEFAULT_MOCK_VOCABULARY)]

        self._accumulated_words.append(word)

        word_timing = MockWordTiming(
            word=word,
            start_time=round(ts, 3),
            end_time=round(ts + 0.02, 3),
            confidence=self._fixed_confidence,
        )

        segment = MockTranscriptSegment(
            segment_id=f"seg_{self._session_id}_{seq}",
            sequence_number=seq,
            text=" ".join(self._accumulated_words),
            start_time=round(ts, 3),
            end_time=round(ts + 0.02, 3),
            is_final=False,
            confidence=self._fixed_confidence,
            words=[word_timing],
        )

        interim_event = MockTranscriptEvent(
            event_id=f"evt_stt_{self._session_id}_interim_{seq}",
            session_id=self._session_id,
            event_type=MockTranscriptEventType.INTERIM,
            timestamp=round(ts + 0.02, 3),
            segment=segment,
        )
        return [interim_event]

    def finish_session(self) -> List[MockTranscriptEvent]:
        """Finalizes active transcription session, emitting FINAL and COMPLETE events."""
        if not self._is_active or self._session_id is None:
            return []

        events: List[MockTranscriptEvent] = []
        full_text = " ".join(self._accumulated_words) if self._accumulated_words else "<silence>"

        final_segment = MockTranscriptSegment(
            segment_id=f"seg_{self._session_id}_final",
            sequence_number=self._chunk_count,
            text=full_text,
            start_time=0.0,
            end_time=round(self._chunk_count * 0.02, 3),
            is_final=True,
            confidence=self._fixed_confidence,
        )

        final_event = MockTranscriptEvent(
            event_id=f"evt_stt_{self._session_id}_final",
            session_id=self._session_id,
            event_type=MockTranscriptEventType.FINAL,
            timestamp=round(self._chunk_count * 0.02, 3),
            segment=final_segment,
        )
        events.append(final_event)

        complete_event = MockTranscriptEvent(
            event_id=f"evt_stt_{self._session_id}_complete",
            session_id=self._session_id,
            event_type=MockTranscriptEventType.COMPLETE,
            timestamp=round(self._chunk_count * 0.02 + 0.01, 3),
        )
        events.append(complete_event)

        self._is_active = False
        return events

    def transcribe_stream(
        self,
        chunks: Iterable[Union[AudioChunk, bytes]],
        session_id: str,
        language: str = "en",
        sample_rate: int = 16000,
    ) -> Iterator[MockTranscriptEvent]:
        """Convenience generator that processes a continuous stream end-to-end."""
        for event in self.start_session(session_id, language, sample_rate):
            yield event
        for chunk in chunks:
            for event in self.process_chunk(chunk):
                yield event
        for event in self.finish_session():
            yield event


# --------------------------------------------------------------------------
# TranscriptionBridge
# Connects AudioPipeline events directly to transcription
# --------------------------------------------------------------------------
class TranscriptionBridge:
    """Connects AudioPipeline events directly to speech transcription.

    Features:
    - Auto-detects whether the team's `sde4_stt` module is available.
    - If `sde4_stt` is unavailable, transparently uses the clearly identified
      :class:`MockTranscriptionAdapter`.
    - Responds to `SpeechStartEvent`, `AudioChunkEvent`, `SpeechEndEvent`,
      and cancellation events.
    - Collects all emitted transcript events for end-to-end verification.
    """

    def __init__(
        self,
        transcriber: Optional[Any] = None,
        auto_flush_on_speech_end: bool = True,
    ) -> None:
        self.auto_flush_on_speech_end: bool = auto_flush_on_speech_end
        self._transcript_events: List[Any] = []
        self._total_chunks_forwarded: int = 0
        self._total_speech_chunks_forwarded: int = 0
        self._active_session_id: Optional[str] = None

        if transcriber is not None:
            self._transcriber = transcriber
            self.is_using_mock_adapter = getattr(transcriber, "is_mock_adapter", False)
        else:
            # Auto-discovery: attempt to import team's sde4_stt module if installed
            try:
                from sde4_stt.adapters.fake_transcriber import FakeTranscriber  # type: ignore

                self._transcriber = FakeTranscriber()
                self.is_using_mock_adapter = False
            except ImportError:
                # Clearly identified mock adapter fallback
                self._transcriber = MockTranscriptionAdapter()
                self.is_using_mock_adapter = True

    @property
    def transcriber(self) -> Any:
        return self._transcriber

    @property
    def transcript_events(self) -> List[Any]:
        return list(self._transcript_events)

    @property
    def total_chunks_forwarded(self) -> int:
        return self._total_chunks_forwarded

    @property
    def total_speech_chunks_forwarded(self) -> int:
        return self._total_speech_chunks_forwarded

    def handle_audio_event(self, event: BaseAudioEvent) -> None:
        """Dispatcher invoked whenever the AudioPipeline emits a :class:`BaseAudioEvent`."""
        if isinstance(event, SpeechStartEvent):
            self._handle_speech_start(event)
        elif isinstance(event, AudioChunkEvent):
            self._handle_audio_chunk(event)
        elif isinstance(event, SpeechEndEvent):
            self._handle_speech_end(event)
        elif isinstance(event, SessionCancelledEvent):
            self._handle_cancellation(event)

    def _handle_speech_start(self, event: SpeechStartEvent) -> None:
        self._active_session_id = event.session_id
        if hasattr(self._transcriber, "start_session") and not getattr(self._transcriber, "is_active", False):
            events = self._transcriber.start_session(session_id=event.session_id)
            if events:
                self._transcript_events.extend(events)

    def _handle_audio_chunk(self, event: AudioChunkEvent) -> None:
        self._total_chunks_forwarded += 1
        if event.is_speech:
            self._total_speech_chunks_forwarded += 1
            if hasattr(self._transcriber, "process_chunk"):
                if not getattr(self._transcriber, "is_active", False):
                    # Start session on first speech chunk if not yet started
                    if hasattr(self._transcriber, "start_session"):
                        init_events = self._transcriber.start_session(session_id=event.session_id)
                        if init_events:
                            self._transcript_events.extend(init_events)
                events = self._transcriber.process_chunk(event.chunk)
                if events:
                    self._transcript_events.extend(events)

    def _handle_speech_end(self, event: SpeechEndEvent) -> None:
        if self.auto_flush_on_speech_end and hasattr(self._transcriber, "finish_session"):
            if getattr(self._transcriber, "is_active", False):
                events = self._transcriber.finish_session()
                if events:
                    self._transcript_events.extend(events)

    def _handle_cancellation(self, event: SessionCancelledEvent) -> None:
        if hasattr(self._transcriber, "finish_session"):
            if getattr(self._transcriber, "is_active", False):
                self._transcriber.finish_session()

    def get_transcript_text(self) -> str:
        """Assemble recognized text across all received FINAL or INTERIM transcript events."""
        final_texts: List[str] = []
        for evt in self._transcript_events:
            seg = getattr(evt, "segment", None)
            if seg and getattr(seg, "is_final", False) and getattr(seg, "text", ""):
                final_texts.append(seg.text)
        if final_texts:
            return " ".join(final_texts)

        # Fallback to last interim text if no final text was emitted
        for evt in reversed(self._transcript_events):
            seg = getattr(evt, "segment", None)
            if seg and getattr(seg, "text", ""):
                return seg.text
        return ""

    def clear(self) -> None:
        """Clear recorded transcript events."""
        self._transcript_events.clear()
        self._total_chunks_forwarded = 0
        self._total_speech_chunks_forwarded = 0
