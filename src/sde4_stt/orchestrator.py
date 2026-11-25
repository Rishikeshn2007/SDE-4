"""
Transcription Orchestrator (Week 2, D8-9).

Connects audio chunks to a provider adapter and produces clean, ordered
transcript events.  Optionally applies preprocessing, retry/error-handling,
and deduplication.

The orchestrator is the single entry point for the STT pipeline::

    from sde4_stt.orchestrator import TranscriptionOrchestrator

    orch = TranscriptionOrchestrator()          # defaults to FakeTranscriber
    result = orch.transcribe(chunks, session_id="demo")
    for seg in result.segments:
        print(seg.text)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable, List, Optional, Union

from academia_audio.schemas import AudioChunk

from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.dedup import EventDeduplicator
from sde4_stt.preprocessing import AudioPreprocessor
from sde4_stt.retry import RetryableAdapter, RetryConfig
from sde4_stt.schemas.transcript import (
    TranscriptError,
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
)

if TYPE_CHECKING:
    from sde4_stt.event_bridge import EventBridgePublisher
    from sde4_stt.session import CancellationToken


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class TranscriptionResult:
    """Immutable container for the output of a transcription run.

    Attributes:
        segments:       Ordered list of final ``TranscriptSegment`` objects.
        events:         Full list of deduplicated ``TranscriptEvent`` objects.
        session_id:     Session identifier used for this run.
        duration_s:     Wall-clock duration of the transcription in seconds.
        chunks_processed: Number of audio chunks fed to the adapter.
        duplicates_suppressed: Count of duplicate events removed.
        interims_reconciled:   Count of interims superseded by finals.
    """

    segments: List[TranscriptSegment] = field(default_factory=list)
    events: List[TranscriptEvent] = field(default_factory=list)
    session_id: str = ""
    duration_s: float = 0.0
    chunks_processed: int = 0
    duplicates_suppressed: int = 0
    interims_reconciled: int = 0

    @property
    def full_text(self) -> str:
        """Concatenated text of all final segments."""
        return " ".join(seg.text for seg in self.segments if seg.text)

    @property
    def has_errors(self) -> bool:
        """True if any ERROR events were emitted."""
        return any(e.event_type == TranscriptEventType.ERROR for e in self.events)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class TranscriptionOrchestrator:
    """End-to-end pipeline: chunks → preprocess → adapter → dedup → result.

    The orchestrator wires together the four Week 2 components:

    1. **AudioPreprocessor** (optional) – resamples/normalises raw PCM.
    2. **RetryableAdapter** (optional) – wraps the adapter with retry logic.
    3. **BaseTranscriberAdapter** – the STT provider (defaults to
       ``FakeTranscriber``).
    4. **EventDeduplicator** – removes duplicates, reconciles interims,
       and orders the output.

    Args:
        adapter:       Concrete adapter.  Defaults to ``FakeTranscriber()``.
        preprocessor:  Optional ``AudioPreprocessor``.  When supplied, every
                       W1 ``AudioChunk`` is preprocessed before being sent
                       to the adapter.
        retry_config:  Optional ``RetryConfig``.  When supplied the adapter
                       is wrapped in a ``RetryableAdapter``.
    """

    def __init__(
        self,
        adapter: Optional[BaseTranscriberAdapter] = None,
        preprocessor: Optional[AudioPreprocessor] = None,
        retry_config: Optional[RetryConfig] = None,
        cancellation_token: Optional["CancellationToken"] = None,
        confidence_threshold: float = 0.0,
        event_publisher: Optional["EventBridgePublisher"] = None,
    ) -> None:
        base_adapter = adapter if adapter is not None else FakeTranscriber()

        # Optionally wrap with retry semantics
        if retry_config is not None:
            self._adapter: BaseTranscriberAdapter = RetryableAdapter(
                base_adapter, retry_config,
            )
        else:
            self._adapter = base_adapter

        self._preprocessor = preprocessor
        self._deduplicator = EventDeduplicator()
        self._cancellation_token = cancellation_token
        self._confidence_threshold = confidence_threshold
        self._event_publisher = event_publisher

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(
        self,
        chunks: Iterable[Union[AudioChunk, bytes]],
        session_id: str,
        language: str = "en",
        sample_rate: int = 16000,
        cancellation_token: Optional[CancellationToken] = None,
        confidence_threshold: Optional[float] = None,
    ) -> TranscriptionResult:
        """Run the full transcription pipeline.

        Steps:
            1. Validate session parameters.
            2. Safely materialise audio input stream from generator.
            3. Start a session on the adapter.
            4. For each chunk: optionally preprocess, then ``process_chunk``.
            5. Finish the session.
            6. Deduplicate and order the collected events.
            7. Return a ``TranscriptionResult``.

        Guarantees that no raw exceptions leak out; provider failures are
        safely captured as structured ERROR events in the result.

        Args:
            chunks:      Iterable of ``AudioChunk`` or raw ``bytes``.
            session_id:  Unique non-empty session identifier.
            language:    BCP-47 language code (default ``"en"``).
            sample_rate: Audio sample rate hint for the adapter.
            cancellation_token: Optional cancellation token for this run.
            confidence_threshold: Optional confidence threshold for this run.

        Returns:
            A ``TranscriptionResult`` containing ordered segments and metadata.
        """
        if cancellation_token is not None:
            self._cancellation_token = cancellation_token
        if confidence_threshold is not None:
            self._confidence_threshold = confidence_threshold

        self._deduplicator.reset()
        wall_start = time.monotonic()
        all_events: List[TranscriptEvent] = []
        chunks_count = 0

        # Stage 0: Validate session parameters
        if not session_id or not isinstance(session_id, str) or not session_id.strip():
            safe_session_id = "invalid_session"
            err_event = TranscriptEvent(
                event_id=f"evt_err_invalid_params_{time.monotonic()}",
                session_id=safe_session_id,
                event_type=TranscriptEventType.ERROR,
                timestamp=time.time(),
                error=TranscriptError(
                    code="INVALID_SESSION_PARAMS",
                    message="session_id must be a non-empty string",
                    recoverable=False,
                ),
            )
            all_events.extend(self._safe_dedup_process([err_event], safe_session_id))
            return TranscriptionResult(
                segments=[],
                events=all_events,
                session_id=safe_session_id,
                duration_s=round(time.monotonic() - wall_start, 4),
                chunks_processed=0,
                duplicates_suppressed=0,
                interims_reconciled=0,
            )

        session_id = session_id.strip()

        # Stage 1: Safely consume audio input generator
        try:
            chunk_list = list(chunks)
        except Exception as exc:
            err_event = TranscriptEvent(
                event_id=f"evt_{session_id}_err_generator",
                session_id=session_id,
                event_type=TranscriptEventType.ERROR,
                timestamp=time.time(),
                error=TranscriptError(
                    code="AUDIO_GENERATOR_FAILED",
                    message=f"Audio input generator error: {exc}",
                    recoverable=False,
                ),
            )
            all_events.extend(self._safe_dedup_process([err_event], session_id))
            return TranscriptionResult(
                segments=[],
                events=all_events,
                session_id=session_id,
                duration_s=round(time.monotonic() - wall_start, 4),
                chunks_processed=0,
                duplicates_suppressed=self._deduplicator.num_duplicates_suppressed,
                interims_reconciled=self._deduplicator.num_interims_reconciled,
            )

        # Sort chunks chronologically if sequence_id or timestamp_s are present (handles out-of-order)
        if any(hasattr(c, "sequence_id") and getattr(c, "sequence_id") is not None for c in chunk_list):
            chunk_list = sorted(
                chunk_list,
                key=lambda c: (
                    getattr(c, "sequence_id", 0) if getattr(c, "sequence_id", None) is not None else 0,
                    getattr(c, "timestamp_s", 0.0) if getattr(c, "timestamp_s", None) is not None else 0.0,
                ),
            )
        elif any(hasattr(c, "timestamp_s") and getattr(c, "timestamp_s") is not None for c in chunk_list):
            chunk_list = sorted(
                chunk_list,
                key=lambda c: getattr(c, "timestamp_s", 0.0) if getattr(c, "timestamp_s", None) is not None else 0.0,
            )

        # Stage 2: Start session safely
        try:
            start_events = self._adapter.start_session(
                session_id, language, sample_rate,
            )
            deduped_start = self._safe_dedup_process(start_events, session_id)
            all_events.extend(deduped_start)
            self._publish_events(deduped_start)
        except Exception as exc:
            err_event = TranscriptEvent(
                event_id=f"evt_{session_id}_err_start",
                session_id=session_id,
                event_type=TranscriptEventType.ERROR,
                timestamp=time.time(),
                error=TranscriptError(
                    code="START_SESSION_FAILED",
                    message=f"Session start failed: {exc}",
                    recoverable=False,
                ),
            )
            deduped_err = self._safe_dedup_process([err_event], session_id)
            all_events.extend(deduped_err)
            self._publish_events(deduped_err)
            self._safe_cleanup_session()
            return TranscriptionResult(
                segments=[],
                events=all_events,
                session_id=session_id,
                duration_s=round(time.monotonic() - wall_start, 4),
                chunks_processed=0,
                duplicates_suppressed=self._deduplicator.num_duplicates_suppressed,
                interims_reconciled=self._deduplicator.num_interims_reconciled,
            )

        # Stage 3: Process chunks
        for idx, chunk in enumerate(chunk_list):
            # --- W3: Check cancellation before each chunk ---
            if self._cancellation_token is not None and self._cancellation_token.is_cancelled:
                cancel_events = []
                try:
                    cancel_events = self._adapter.cancel()
                except Exception:
                    # Fallback: emit CANCELLED event manually if adapter lacks cancel()
                    cancel_events = [
                        TranscriptEvent(
                            event_id=f"evt_{session_id}_cancelled_{idx}",
                            session_id=session_id,
                            event_type=TranscriptEventType.CANCELLED,
                            timestamp=time.time(),
                        )
                    ]
                cancel_events = cancel_events or [
                    TranscriptEvent(
                        event_id=f"evt_{session_id}_cancelled_{idx}",
                        session_id=session_id,
                        event_type=TranscriptEventType.CANCELLED,
                        timestamp=time.time(),
                    )
                ]
                deduped_cancel = self._safe_dedup_process(cancel_events, session_id)
                all_events.extend(deduped_cancel)
                self._publish_events(deduped_cancel)
                return TranscriptionResult(
                    segments=[],
                    events=all_events,
                    session_id=session_id,
                    duration_s=round(time.monotonic() - wall_start, 4),
                    chunks_processed=chunks_count,
                    duplicates_suppressed=self._deduplicator.num_duplicates_suppressed,
                    interims_reconciled=self._deduplicator.num_interims_reconciled,
                )

            if self._has_fatal_error(all_events):
                break

            is_last = idx == len(chunk_list) - 1

            # Preprocess AudioChunks when a preprocessor is configured
            if self._preprocessor is not None and isinstance(chunk, AudioChunk):
                try:
                    chunk = self._preprocessor.process_chunk(chunk)
                except Exception as exc:
                    err_event = TranscriptEvent(
                        event_id=f"evt_{session_id}_err_preproc_{idx}",
                        session_id=session_id,
                        event_type=TranscriptEventType.ERROR,
                        timestamp=time.time(),
                        error=TranscriptError(
                            code="PREPROCESSING_FAILED",
                            message=f"Preprocessing failed: {exc}",
                            recoverable=False,
                        ),
                    )
                    deduped = self._safe_dedup_process([err_event], session_id)
                    all_events.extend(deduped)
                    self._publish_events(deduped)
                    self._safe_cleanup_session()
                    break

            # Feed to adapter safely
            try:
                try:
                    chunk_events = self._adapter.process_chunk(chunk, is_last=is_last)
                except TypeError:
                    chunk_events = self._adapter.process_chunk(chunk)
            except Exception as exc:
                err_event = TranscriptEvent(
                    event_id=f"evt_{session_id}_err_chunk_{idx}",
                    session_id=session_id,
                    event_type=TranscriptEventType.ERROR,
                    timestamp=time.time(),
                    error=TranscriptError(
                        code="CHUNK_PROCESSING_FAILED",
                        message=f"Chunk processing failed: {exc}",
                        recoverable=False,
                    ),
                )
                chunk_events = [err_event]

            # --- W3: low-confidence flagging ---
            extra_events = self._check_low_confidence(chunk_events, session_id)
            chunk_events = chunk_events + extra_events

            deduped_chunk = self._safe_dedup_process(chunk_events, session_id)
            all_events.extend(deduped_chunk)
            self._publish_events(deduped_chunk)
            chunks_count += 1

            if self._has_fatal_error(chunk_events):
                self._safe_cleanup_session()
                break

        # Stage 4: Finish session (only if no error occurred)
        if not self._has_fatal_error(all_events):
            try:
                finish_events = self._adapter.finish_session()
                # W3: low-confidence flagging on finish events as well
                extra_events = self._check_low_confidence(finish_events, session_id)
                finish_events = finish_events + extra_events
                deduped_finish = self._safe_dedup_process(finish_events, session_id)
                all_events.extend(deduped_finish)
                self._publish_events(deduped_finish)
            except Exception as exc:
                err_event = TranscriptEvent(
                    event_id=f"evt_{session_id}_err_finish",
                    session_id=session_id,
                    event_type=TranscriptEventType.ERROR,
                    timestamp=time.time(),
                    error=TranscriptError(
                        code="FINISH_SESSION_FAILED",
                        message=f"Session finish failed: {exc}",
                        recoverable=False,
                    ),
                )
                deduped_err = self._safe_dedup_process([err_event], session_id)
                all_events.extend(deduped_err)
                self._publish_events(deduped_err)
                self._safe_cleanup_session()

        # Stage 5: Ordered finals (only if pipeline did not fail with error)
        if self._has_fatal_error(all_events):
            ordered_segments = []
        else:
            ordered_segments = self._deduplicator.get_ordered_finals()

        wall_elapsed = time.monotonic() - wall_start

        return TranscriptionResult(
            segments=ordered_segments,
            events=all_events,
            session_id=session_id,
            duration_s=round(wall_elapsed, 4),
            chunks_processed=chunks_count,
            duplicates_suppressed=self._deduplicator.num_duplicates_suppressed,
            interims_reconciled=self._deduplicator.num_interims_reconciled,
        )

    def _safe_dedup_process(
        self,
        events: List[TranscriptEvent],
        session_id: str,
    ) -> List[TranscriptEvent]:
        """Safely process events through the deduplicator."""
        try:
            return self._deduplicator.process_events(events)
        except Exception as exc:
            return [
                TranscriptEvent(
                    event_id=f"evt_{session_id}_err_dedup_{time.monotonic()}",
                    session_id=session_id,
                    event_type=TranscriptEventType.ERROR,
                    timestamp=time.time(),
                    error=TranscriptError(
                        code="EVENT_PROCESSING_FAILED",
                        message=f"Event processing error: {exc}",
                        recoverable=False,
                    ),
                )
            ]

    def _safe_cleanup_session(self) -> None:
        """Safely clean up active adapter session on errors."""
        if getattr(self._adapter, "is_active", False):
            try:
                self._adapter.finish_session()
            except Exception:
                pass
        if hasattr(self._adapter, "close") and callable(self._adapter.close):
            try:
                self._adapter.close()
            except Exception:
                pass

    @staticmethod
    def _has_fatal_error(events: List[TranscriptEvent]) -> bool:
        """Return True if any event in the list represents an unrecoverable ERROR."""
        return any(
            e.event_type == TranscriptEventType.ERROR
            and (e.error is None or not e.error.recoverable)
            for e in events
        )

    def _publish_events(self, events: List[TranscriptEvent]) -> None:
        """Forward events to the event publisher if one is configured."""
        if self._event_publisher is not None:
            self._event_publisher.publish_many(events)

    def _check_low_confidence(
        self,
        events: List[TranscriptEvent],
        session_id: str,
    ) -> List[TranscriptEvent]:
        """Return additional ERROR events for low-confidence FINAL segments.

        When ``confidence_threshold > 0`` and a FINAL segment's confidence
        falls below the threshold, an extra ERROR event is emitted alongside
        the FINAL event so consumers can act on it.  The FINAL itself is NOT
        suppressed.
        """
        if self._confidence_threshold <= 0.0:
            return []

        extra: List[TranscriptEvent] = []
        for event in events:
            if (
                event.event_type == TranscriptEventType.FINAL
                and event.segment is not None
                and event.segment.confidence < self._confidence_threshold
            ):
                extra.append(
                    TranscriptEvent(
                        event_id=f"evt_{session_id}_low_conf_{event.segment.segment_id}",
                        session_id=session_id,
                        event_type=TranscriptEventType.ERROR,
                        timestamp=time.time(),
                        error=TranscriptError(
                            code="LOW_CONFIDENCE",
                            message=(
                                f"Segment '{event.segment.segment_id}' confidence "
                                f"{event.segment.confidence:.3f} is below threshold "
                                f"{self._confidence_threshold:.3f}."
                            ),
                            recoverable=True,
                            details={
                                "segment_id": event.segment.segment_id,
                                "confidence": event.segment.confidence,
                                "threshold": self._confidence_threshold,
                            },
                        ),
                    )
                )
        return extra

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def adapter(self) -> BaseTranscriberAdapter:
        """The underlying (possibly wrapped) adapter."""
        return self._adapter

    @property
    def preprocessor(self) -> Optional[AudioPreprocessor]:
        """The configured preprocessor, or ``None``."""
        return self._preprocessor


__all__ = ["TranscriptionOrchestrator", "TranscriptionResult"]
