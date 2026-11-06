"""
Real Speech Transcriber Adapter for SDE 4 Speech-to-Text Pipeline.

Uses speech_recognition (Google Web Speech API) to transcribe real spoken audio
into standardized TranscriptEvent and TranscriptSegment objects.

Requires no paid API keys, but **requires an active internet connection**.
Google ``recognize_google()`` is an HTTP-based cloud service; it does NOT work
offline.  For offline / unit-test usage, use :class:`FakeTranscriber` instead.

Architecture notes
------------------
1. **Buffered batch recognition, not streaming**.
   ``process_chunk()`` accumulates raw PCM bytes in memory.  Recognition is
   deferred until ``finish_session()`` sends the complete buffer to Google's
   Web Speech endpoint as a single HTTP request.  This is fundamentally
   different from bidirectional-streaming providers (e.g. Google Cloud Speech
   v2 gRPC, Deepgram WebSockets) that return interim hypotheses as audio
   arrives.

2. **No interim events emitted**.
   ``process_chunk()`` always returns an empty list.  Interim transcription
   would require a streaming protocol not available through the free
   ``speech_recognition`` library.  Explicit ``finish_session()`` is the
   sole trigger for recognition and event emission.

3. **No provider confidence or word timestamps**.
   ``recognize_google()`` (the string-only variant used here) returns plain
   text; it does not supply confidence scores or word-level timing
   information.  Segment confidence is left at the schema default (``1.0``)
   and annotated accordingly.  Word timings, if included, carry **estimated**
   timestamps derived by dividing the total audio duration equally among
   the recognised words — not genuine provider-supplied alignments.

4. **True streaming with interim hypotheses** requires a commercial streaming
   API (Google Cloud Speech v2, Deepgram, AssemblyAI, etc.) and is out of
   scope for this free-tier adapter.
"""

import time
from typing import List, Optional, Union

from academia_audio.schemas import AudioChunk
from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.schemas.transcript import (
    TranscriptError,
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
    WordTiming,
)


class RealSpeechTranscriber(BaseTranscriberAdapter):
    """
    Real Speech Transcriber adapter implementing :class:`BaseTranscriberAdapter`.

    Converts real spoken microphone audio into typed :class:`TranscriptSegment`
    and :class:`TranscriptEvent` instances using Google Web Speech Recognition
    (free, no API key required, **internet connection required**).

    Limitations
    -----------
    * Recognition requires an active internet connection; this is NOT an
      offline transcriber.  Use :class:`~sde4_stt.adapters.FakeTranscriber`
      for offline testing.
    * ``process_chunk()`` returns an empty list on every call; no interim
      events are produced.
    * Confidence scores are not supplied by ``recognize_google()`` in its
      plain-text mode.  :attr:`TranscriptSegment.confidence` is set to the
      schema default (``1.0``) and must NOT be interpreted as a measured
      provider confidence value.
    * Word-level timestamps are **estimates** computed by equally dividing
      the total audio duration among the recognised words.  They are not
      genuine provider-supplied word alignments.
    """

    def __init__(
        self,
        language: str = "en-US",
        sample_rate: int = 16000,
        sample_width: int = 2,  # 16-bit PCM
    ):
        """
        Initialise the adapter, lazily importing ``speech_recognition``.

        Parameters
        ----------
        language:
            BCP-47 language tag forwarded to ``recognize_google()``.
        sample_rate:
            PCM sample rate in Hz (default 16 000).
        sample_width:
            Bytes per sample (default 2 for 16-bit PCM).

        Raises
        ------
        ImportError
            If the ``SpeechRecognition`` package is not installed.  Install it
            with ``pip install .[google-stt]`` or ``pip install SpeechRecognition``.
        """
        try:
            import speech_recognition as sr
        except ImportError as exc:
            raise ImportError(
                "SpeechRecognition is required for RealSpeechTranscriber. "
                "Install it with: pip install .[google-stt] or pip install SpeechRecognition"
            ) from exc

        super().__init__(provider_name="real-speech-recognizer")
        self._sr = sr
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
        """
        Initialise a new recognition session and clear the audio buffer.

        Parameters
        ----------
        session_id:
            Non-empty identifier for this session.
        language:
            BCP-47 language tag (overrides the constructor value for this
            session).
        sample_rate:
            PCM sample rate in Hz.

        Returns
        -------
        List[TranscriptEvent]
            A single :attr:`TranscriptEventType.START` event.
        """
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
        is_last: bool = False,
    ) -> List[TranscriptEvent]:
        """
        Buffer an audio chunk for later batch recognition.

        Audio bytes are appended to an internal buffer.  No network call is
        made and no transcript events are emitted; this method **always returns
        an empty list**.

        Callers must invoke :meth:`finish_session` to trigger recognition and
        receive :attr:`TranscriptEventType.FINAL` / :attr:`TranscriptEventType.COMPLETE`
        events.  The ``is_last`` flag is accepted for interface compatibility
        but is intentionally ignored here: explicit ``finish_session()`` is the
        sole mechanism for flushing the buffer.  This avoids ambiguous
        double-flush behaviour that would arise if ``process_chunk`` and
        ``finish_session`` both attempted recognition on the same buffer.

        Parameters
        ----------
        chunk:
            An :class:`~academia_audio.schemas.AudioChunk` or raw ``bytes``
            containing PCM audio data.
        is_last:
            Accepted for interface compatibility; has no effect.  Call
            :meth:`finish_session` explicitly to finalise the session.

        Returns
        -------
        List[TranscriptEvent]
            Always ``[]``.

        Raises
        ------
        RuntimeError
            If called without a prior :meth:`start_session`.
        TypeError
            If ``chunk`` is not an :class:`~academia_audio.schemas.AudioChunk`
            or ``bytes``-like object.
        """
        if not self._is_active or self._session_id is None:
            raise RuntimeError(
                "Cannot process chunks without an active session. "
                "Call start_session() first."
            )

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
        """
        Send the accumulated audio buffer to Google Web Speech and emit events.

        Recognition is performed as a single HTTP request via
        ``recognize_google()``.  The service **requires an internet
        connection**; a :attr:`TranscriptEventType.ERROR` event is emitted if
        the request fails.

        Confidence and word timestamps
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ``recognize_google()`` (plain-text variant) returns only the
        transcribed string — no confidence scores and no word-level alignments.

        * :attr:`TranscriptSegment.confidence` is left at the schema default
          value (``1.0``).  This is **not** a provider-measured confidence; it
          is simply the Pydantic field default and should not be used as a
          reliability indicator.
        * Word-level :class:`WordTiming` objects are generated by equally
          dividing the total audio duration among the recognised words.  These
          are **estimated** timestamps, not genuine Google-supplied word
          alignments.  :attr:`WordTiming.confidence` is ``None`` to avoid
          fabricating per-word scores.

        Returns
        -------
        List[TranscriptEvent]
            * On success: ``[FINAL, COMPLETE]``
            * On empty buffer: ``[COMPLETE]``
            * On recognition failure: ``[ERROR, COMPLETE]``
        """
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
        audio_data = self._sr.AudioData(
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
        except self._sr.UnknownValueError:
            transcription_error = (
                "Could not understand audio (silence or unintelligible speech)."
            )
        except self._sr.RequestError as exc:
            transcription_error = f"Speech recognition service error: {exc}"
        except Exception as exc:
            transcription_error = f"Recognition error: {exc}"

        # Total audio duration in seconds (derived from PCM geometry)
        duration = round(
            len(raw_bytes) / (self._sample_rate * self._sample_width), 3
        )

        if recognized_text and recognized_text.strip():
            words = recognized_text.strip().split()
            word_duration = duration / max(1, len(words))

            # Word timestamps are ESTIMATED by equal division of total duration.
            # They are not genuine Google-supplied word-level alignments.
            # confidence is None because recognize_google() does not supply it.
            word_timings = [
                WordTiming(
                    word=w,
                    start_time=round(i * word_duration, 3),
                    end_time=round((i + 1) * word_duration, 3),
                    confidence=None,  # not available from recognize_google()
                )
                for i, w in enumerate(words)
            ]

            # confidence uses the schema default (1.0); it is NOT a provider
            # measurement — recognize_google() (plain-text mode) does not
            # supply confidence scores.
            final_segment = TranscriptSegment(
                segment_id=f"seg_{self._session_id}_final",
                sequence_number=self._chunk_count,
                text=recognized_text.strip(),
                start_time=0.0,
                end_time=duration,
                is_final=True,
                # Schema default; NOT a provider-measured confidence score.
                confidence=1.0,
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
