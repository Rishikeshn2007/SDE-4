"""
Real Speech Transcriber Adapter for SDE 4 Speech-to-Text Pipeline.

Uses speech_recognition (Google Web Speech API / offline capable) to transcribe
actual real-world speech recorded from a microphone or audio stream into
standardized, validated TranscriptEvent and TranscriptSegment objects.
Requires no paid API keys.
"""

import time
from typing import List, Optional, Union
import speech_recognition as sr

from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.schemas.audio import AudioChunk
from sde4_stt.schemas.transcript import (
    TranscriptError,
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
    WordTiming,
)


class RealSpeechTranscriber(BaseTranscriberAdapter):
    """
    Real Speech Transcriber adapter implementing BaseTranscriberAdapter.

    Converts real spoken microphone audio into typed TranscriptSegment and
    TranscriptEvent instances using Google Speech Recognition (free, no API key).
    """

    def __init__(
        self,
        language: str = "en-US",
        sample_rate: int = 16000,
        sample_width: int = 2,  # 16-bit PCM
    ):
        super().__init__(provider_name="real-speech-recognizer")
        self._language = language
        self._sample_rate = sample_rate
        self._sample_width = sample_width
        self._recognizer = sr.Recognizer()
        self._audio_buffer = bytearray()
        self._start_time = 0.0
        self._chunk_count = 0

    def start_session(
        self,
        session_id: str,
        language: str = "en-US",
        sample_rate: int = 16000,
    ) -> List[TranscriptEvent]:
        """Initializes a new real-world speech recognition session."""
        if not session_id or not session_id.strip():
            raise ValueError("session_id must be non-empty")

        self._session_id = session_id.strip()
        self._language = language or "en-US"
        self._sample_rate = sample_rate or 16000
        self._is_active = True
        self._audio_buffer.clear()
        self._chunk_count = 0
        self._start_time = time.time()

        start_event = TranscriptEvent(
            event_id=f"evt_{self._session_id}_start",
            session_id=self._session_id,
            event_type=TranscriptEventType.START,
            timestamp=self._start_time,
        )
        return [start_event]

    def process_chunk(
        self,
        chunk: Union[AudioChunk, bytes],
    ) -> List[TranscriptEvent]:
        """Buffers audio chunks and emits interim status."""
        if not self._is_active or self._session_id is None:
            raise RuntimeError("Cannot process chunks without an active session. Call start_session() first.")

        if isinstance(chunk, AudioChunk):
            data = chunk.data
        elif hasattr(chunk, "data") and isinstance(chunk.data, (bytes, bytearray)):
            data = bytes(chunk.data)
        elif isinstance(chunk, (bytes, bytearray)):
            data = bytes(chunk)
        else:
            raise TypeError(f"Unsupported chunk type: {type(chunk).__name__}")

        self._audio_buffer.extend(data)
        self._chunk_count += 1
        return []

    def finish_session(self) -> List[TranscriptEvent]:
        """Transcribes the accumulated real audio and emits FINAL and COMPLETE events."""
        if not self._is_active or self._session_id is None:
            raise RuntimeError("Session is not active.")

        now = time.time()
        events: List[TranscriptEvent] = []
        raw_bytes = bytes(self._audio_buffer)

        if not raw_bytes:
            events.append(
                TranscriptEvent(
                    event_id=f"evt_{self._session_id}_complete",
                    session_id=self._session_id,
                    event_type=TranscriptEventType.COMPLETE,
                    timestamp=now,
                )
            )
            self._is_active = False
            return events

        # Wrap in SpeechRecognition AudioData
        audio_data = sr.AudioData(
            raw_bytes,
            sample_rate=self._sample_rate,
            sample_width=self._sample_width,
        )

        recognized_text = ""
        transcription_error: Optional[str] = None

        try:
            recognized_text = self._recognizer.recognize_google(
                audio_data,
                language=self._language,
            )
        except sr.UnknownValueError:
            transcription_error = "Could not understand audio (silence or unintelligible speech)."
        except sr.RequestError as exc:
            transcription_error = f"Speech recognition service error: {exc}"
        except Exception as exc:
            transcription_error = f"Recognition error: {exc}"

        duration = round(len(raw_bytes) / (self._sample_rate * self._sample_width), 3)

        if recognized_text and recognized_text.strip():
            words = recognized_text.strip().split()
            word_duration = duration / max(1, len(words))
            word_timings = [
                WordTiming(
                    word=w,
                    start_time=round(i * word_duration, 3),
                    end_time=round((i + 1) * word_duration, 3),
                    confidence=0.95,
                )
                for i, w in enumerate(words)
            ]

            final_segment = TranscriptSegment(
                segment_id=f"seg_{self._session_id}_final",
                sequence_number=self._chunk_count,
                text=recognized_text.strip(),
                start_time=0.0,
                end_time=duration,
                is_final=True,
                confidence=0.95,
                language=self._language,
                words=word_timings,
            )

            events.append(
                TranscriptEvent(
                    event_id=f"evt_{self._session_id}_final",
                    session_id=self._session_id,
                    event_type=TranscriptEventType.FINAL,
                    timestamp=now,
                    segment=final_segment,
                )
            )
        elif transcription_error:
            events.append(
                TranscriptEvent(
                    event_id=f"evt_{self._session_id}_err",
                    session_id=self._session_id,
                    event_type=TranscriptEventType.ERROR,
                    timestamp=now,
                    error=TranscriptError(
                        code="STT_RECOGNITION_FAILED",
                        message=transcription_error,
                        recoverable=True,
                    ),
                )
            )

        events.append(
            TranscriptEvent(
                event_id=f"evt_{self._session_id}_complete",
                session_id=self._session_id,
                event_type=TranscriptEventType.COMPLETE,
                timestamp=now + 0.01,
            )
        )

        self._is_active = False
        return events
