"""Audio pipeline lifecycle controller and state machine (Week 2 & Week 3).

Coordinates the DeviceAdapter, BoundedAudioBuffer, VAD, and Transcription components
while strictly enforcing valid state transitions (start, pause, resume, stop, cancel),
handling device-loss detection/reconnection without crashing, emitting strictly ordered
speech and normalized audio events, and guaranteeing proper buffer cleanup upon termination.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Callable, List, Optional, Tuple

from .buffer import BoundedAudioBuffer
from .device import DeviceAdapter, MockDeviceAdapter
from .normalization import normalize_audio_chunk
from .schemas import (
    AudioChunk,
    AudioChunkEvent,
    AudioError,
    AudioErrorCode,
    AudioEventType,
    AudioFormat,
    BaseAudioEvent,
    DeviceDisconnectedEvent,
    DeviceReconnectedEvent,
    SessionCancelledEvent,
    SpeechEndEvent,
    SpeechStartEvent,
    _validate_id,
)
from .vad import BaseVAD, MockVAD, VADResult


class LifecycleState(str, Enum):
    """Execution state of the audio pipeline."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    RECOVERING = "recovering"
    CANCELLED = "cancelled"


class AudioPipeline:
    """Manages audio capture lifecycle, buffering, VAD, order verification, and speech events.

    Enforces the following state machine:
        * STOPPED -> RUNNING via :meth:`start`
        * RUNNING -> PAUSED via :meth:`pause`
        * PAUSED  -> RUNNING via :meth:`resume`
        * RUNNING -> STOPPED via :meth:`stop`
        * PAUSED  -> STOPPED via :meth:`stop`
        * RUNNING/PAUSED/RECOVERING -> CANCELLED via :meth:`cancel`
        * RUNNING -> RECOVERING upon device disconnection
        * RECOVERING -> RUNNING upon successful device reconnection

    All invalid transitions are considered illegal and raise :class:`AudioError`
    with code ``AudioErrorCode.ILLEGAL_STATE_TRANSITION``.

    Parameters:
        adapter:               Audio input adapter (defaults to :class:`MockDeviceAdapter`).
        buffer:                Bounded buffer (defaults to capacity=50).
        vad:                   Voice Activity Detector (defaults to :class:`MockVAD`).
        fmt:                   Target audio format (defaults to 16 kHz mono).
        strict_gap_detection:  If True, raises an AudioError when a sequence ID gap is detected.
        auto_reconnect:        If True, attempts automatic device recovery when device loss is detected.
        max_reconnect_attempts:Maximum automatic reconnection attempts before giving up.
    """

    def __init__(
        self,
        adapter: Optional[DeviceAdapter] = None,
        buffer: Optional[BoundedAudioBuffer] = None,
        vad: Optional[BaseVAD] = None,
        fmt: Optional[AudioFormat] = None,
        strict_gap_detection: bool = False,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 3,
    ) -> None:
        self.fmt: AudioFormat = fmt if fmt is not None else AudioFormat(16000, 1)
        self.adapter: DeviceAdapter = adapter if adapter is not None else MockDeviceAdapter()
        self.buffer: BoundedAudioBuffer = buffer if buffer is not None else BoundedAudioBuffer(capacity=50)
        self.vad: BaseVAD = vad if vad is not None else MockVAD()
        self.strict_gap_detection: bool = strict_gap_detection
        self.auto_reconnect: bool = auto_reconnect
        self.max_reconnect_attempts: int = max_reconnect_attempts

        self._state: LifecycleState = LifecycleState.STOPPED
        self._last_chunk: Optional[AudioChunk] = None
        self._gaps_detected: int = 0
        self._late_chunks_detected: int = 0
        self._total_chunks_processed: int = 0

        # Week 3 State: Session, Event Tracking, Speech State Machine & Device Recovery
        self._session_id: str = "sess_default"
        self._correlation_id: str = "corr_default"
        self._event_seq: int = 0
        self._events: List[BaseAudioEvent] = []
        self._listeners: List[Callable[[BaseAudioEvent], None]] = []
        self._transcription_sinks: List[object] = []
        self._in_speech: bool = False
        self._speech_start_time: float = 0.0
        self._device_disconnections_detected: int = 0
        self._device_reconnections_successful: int = 0
        self._reconnect_attempts: int = 0

    @property
    def state(self) -> LifecycleState:
        """Current lifecycle state."""
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == LifecycleState.RUNNING

    @property
    def is_paused(self) -> bool:
        return self._state == LifecycleState.PAUSED

    @property
    def is_stopped(self) -> bool:
        return self._state in (LifecycleState.STOPPED, LifecycleState.CANCELLED)

    @property
    def is_recovering(self) -> bool:
        return self._state == LifecycleState.RECOVERING

    @property
    def is_cancelled(self) -> bool:
        return self._state == LifecycleState.CANCELLED

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def correlation_id(self) -> str:
        return self._correlation_id

    @property
    def events(self) -> List[BaseAudioEvent]:
        """All pipeline events emitted during the current session in chronological order."""
        return list(self._events)

    @property
    def gaps_detected(self) -> int:
        """Count of detected audio gaps (missing sequence IDs)."""
        return self._gaps_detected

    @property
    def late_chunks_detected(self) -> int:
        """Count of late or out-of-order chunks received."""
        return self._late_chunks_detected

    @property
    def total_chunks_processed(self) -> int:
        """Total chunks successfully evaluated by VAD and buffered."""
        return self._total_chunks_processed

    @property
    def device_disconnections_detected(self) -> int:
        """Count of detected device disconnection events."""
        return self._device_disconnections_detected

    @property
    def device_reconnections_successful(self) -> int:
        """Count of successful device reconnections."""
        return self._device_reconnections_successful

    def add_event_listener(self, listener: Callable[[BaseAudioEvent], None]) -> None:
        """Register a callback that receives every emitted :class:`BaseAudioEvent`."""
        self._listeners.append(listener)

    def attach_transcription_sink(self, sink: object) -> None:
        """Attach a transcription bridge or sink that receives pipeline events."""
        self._transcription_sinks.append(sink)

    def _next_event_seq(self) -> int:
        seq = self._event_seq
        self._event_seq += 1
        return seq

    def _generate_event_id(self) -> str:
        return f"evt_{self._session_id}_{self._event_seq}"

    def _emit_event(self, event: BaseAudioEvent) -> None:
        """Internal helper to record and broadcast events."""
        self._events.append(event)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass
        for sink in self._transcription_sinks:
            if hasattr(sink, "handle_audio_event"):
                try:
                    sink.handle_audio_event(event)
                except Exception:
                    pass

    def start(
        self,
        session_id: str = "sess_default",
        correlation_id: Optional[str] = None,
    ) -> None:
        """Transition from STOPPED or CANCELLED to RUNNING, opening the audio adapter.

        Args:
            session_id:     Unique identifier for this audio session (non-empty).
            correlation_id: Tracing correlation ID (generated if not provided).

        Raises:
            AudioError: ILLEGAL_STATE_TRANSITION if not in STOPPED or CANCELLED state.
            AudioError: PERMISSION_DENIED or DEVICE_UNSUPPORTED if adapter fails.
            AudioError: INVALID_PARAMETER if session_id or correlation_id is invalid.
        """
        if self._state not in (LifecycleState.STOPPED, LifecycleState.CANCELLED):
            raise AudioError(
                AudioErrorCode.ILLEGAL_STATE_TRANSITION,
                f"Cannot start audio pipeline: current state is '{self._state.value}' (expected 'stopped')",
            )

        self._session_id = _validate_id("session_id", session_id)
        if correlation_id is not None:
            self._correlation_id = _validate_id("correlation_id", correlation_id)
        else:
            self._correlation_id = f"corr_{self._session_id}_{uuid.uuid4().hex[:8]}"

        self._event_seq = 0
        self._events.clear()
        self._in_speech = False
        self._speech_start_time = 0.0
        self._reconnect_attempts = 0

        try:
            self.adapter.open(self.fmt)
        except AudioError:
            self._state = LifecycleState.STOPPED
            raise

        self._state = LifecycleState.RUNNING
        self._last_chunk = None

    def pause(self) -> None:
        """Transition from RUNNING to PAUSED.

        Raises:
            AudioError: ILLEGAL_STATE_TRANSITION if not in RUNNING state.
        """
        if self._state != LifecycleState.RUNNING:
            raise AudioError(
                AudioErrorCode.ILLEGAL_STATE_TRANSITION,
                f"Cannot pause audio pipeline: current state is '{self._state.value}' (expected 'running')",
            )
        self._state = LifecycleState.PAUSED

    def resume(self) -> None:
        """Transition from PAUSED to RUNNING.

        Raises:
            AudioError: ILLEGAL_STATE_TRANSITION if not in PAUSED state.
        """
        if self._state != LifecycleState.PAUSED:
            raise AudioError(
                AudioErrorCode.ILLEGAL_STATE_TRANSITION,
                f"Cannot resume audio pipeline: current state is '{self._state.value}' (expected 'paused')",
            )
        self._state = LifecycleState.RUNNING

    def stop(self) -> None:
        """Transition from RUNNING, PAUSED, or RECOVERING to STOPPED.

        Closes the audio device adapter and releases all buffered chunks.

        Raises:
            AudioError: ILLEGAL_STATE_TRANSITION if already in STOPPED state.
        """
        if self._state == LifecycleState.STOPPED:
            raise AudioError(
                AudioErrorCode.ILLEGAL_STATE_TRANSITION,
                "Cannot stop audio pipeline: already in 'stopped' state",
            )

        try:
            # If stopped while in speech, emit final SpeechEndEvent to maintain event ordering
            if self._in_speech and self._last_chunk is not None:
                end_time = self._last_chunk.timestamp_s + self._last_chunk.duration_s
                dur = max(0.0, end_time - self._speech_start_time)
                end_evt = SpeechEndEvent(
                    event_id=self._generate_event_id(),
                    session_id=self._session_id,
                    correlation_id=self._correlation_id,
                    event_type=AudioEventType.SPEECH_END,
                    timestamp_s=end_time,
                    sequence_id=self._next_event_seq(),
                    speech_start_time_s=self._speech_start_time,
                    speech_end_time_s=end_time,
                    duration_s=round(dur, 4),
                )
                self._emit_event(end_evt)
                self._in_speech = False

            self.adapter.close()
        finally:
            # Acceptance Criterion: Stop releases the buffer.
            self.buffer.release()
            self.vad.reset()
            self._state = LifecycleState.STOPPED
            self._last_chunk = None

    def cancel(self, reason: str = "User cancelled session") -> None:
        """Transition from RUNNING, PAUSED, or RECOVERING to CANCELLED.

        Stops capture immediately and releases all buffered chunks.

        Raises:
            AudioError: ILLEGAL_STATE_TRANSITION if already in STOPPED or CANCELLED state.
        """
        if self._state in (LifecycleState.STOPPED, LifecycleState.CANCELLED):
            raise AudioError(
                AudioErrorCode.ILLEGAL_STATE_TRANSITION,
                f"Cannot cancel audio pipeline: already in '{self._state.value}' state",
            )

        try:
            curr_ts = self._last_chunk.timestamp_s if self._last_chunk is not None else 0.0

            # If cancelled mid-utterance, emit SpeechEndEvent first to close utterance properly
            if self._in_speech:
                dur = max(0.0, curr_ts - self._speech_start_time)
                end_evt = SpeechEndEvent(
                    event_id=self._generate_event_id(),
                    session_id=self._session_id,
                    correlation_id=self._correlation_id,
                    event_type=AudioEventType.SPEECH_END,
                    timestamp_s=curr_ts,
                    sequence_id=self._next_event_seq(),
                    speech_start_time_s=self._speech_start_time,
                    speech_end_time_s=curr_ts,
                    duration_s=round(dur, 4),
                )
                self._emit_event(end_evt)
                self._in_speech = False

            # Emit SessionCancelledEvent
            cancel_evt = SessionCancelledEvent(
                event_id=self._generate_event_id(),
                session_id=self._session_id,
                correlation_id=self._correlation_id,
                event_type=AudioEventType.SESSION_CANCELLED,
                timestamp_s=curr_ts,
                sequence_id=self._next_event_seq(),
                reason=reason,
            )
            self._emit_event(cancel_evt)

            self.adapter.close()
        finally:
            # Strict Acceptance Criterion: Cancellation must stop capture and release the buffer.
            self.buffer.release()
            self.vad.reset()
            self._state = LifecycleState.CANCELLED
            self._last_chunk = None

    def recover_device(self, new_device_id: Optional[str] = None) -> bool:
        """Attempt safe reconnection to the audio device without crashing.

        Args:
            new_device_id: Optional fallback device ID if the original device is permanently lost.

        Returns:
            True if reconnection succeeded and pipeline transitioned back to RUNNING.
            False if reconnection failed.
        """
        if self._state not in (LifecycleState.RECOVERING, LifecycleState.RUNNING):
            raise AudioError(
                AudioErrorCode.ILLEGAL_STATE_TRANSITION,
                f"Cannot recover device in '{self._state.value}' state (expected 'recovering' or 'running')",
            )

        self._reconnect_attempts += 1
        try:
            success = self.adapter.reconnect(device_id=new_device_id)
            if success:
                self._state = LifecycleState.RUNNING
                self._device_reconnections_successful += 1
                curr_ts = self._last_chunk.timestamp_s if self._last_chunk is not None else 0.0
                active_dev = getattr(self.adapter.get_selected_device(), "id", "mock-default")
                reconn_evt = DeviceReconnectedEvent(
                    event_id=self._generate_event_id(),
                    session_id=self._session_id,
                    correlation_id=self._correlation_id,
                    event_type=AudioEventType.DEVICE_RECONNECTED,
                    timestamp_s=curr_ts,
                    sequence_id=self._next_event_seq(),
                    device_id=active_dev,
                    reconnect_attempts=self._reconnect_attempts,
                )
                self._emit_event(reconn_evt)
                return True
            return False
        except Exception:
            # Remain in RECOVERING safely without unhandled crashes
            return False

    def _handle_device_loss(self, exc: AudioError) -> Optional[Tuple[AudioChunk, VADResult]]:
        """Handles device loss detection gracefully without crashing."""
        self._device_disconnections_detected += 1
        self._state = LifecycleState.RECOVERING

        curr_ts = self._last_chunk.timestamp_s if self._last_chunk is not None else 0.0
        active_dev = getattr(self.adapter.get_selected_device(), "id", "mock-default")

        # Emit DeviceDisconnectedEvent
        disc_evt = DeviceDisconnectedEvent(
            event_id=self._generate_event_id(),
            session_id=self._session_id,
            correlation_id=self._correlation_id,
            event_type=AudioEventType.DEVICE_DISCONNECTED,
            timestamp_s=curr_ts,
            sequence_id=self._next_event_seq(),
            device_id=active_dev,
            reason=exc.message,
        )
        self._emit_event(disc_evt)

        # Attempt recovery if auto_reconnect is configured
        if self.auto_reconnect and self._reconnect_attempts < self.max_reconnect_attempts:
            recovered = self.recover_device()
            if recovered:
                # Reconnection succeeded: continue processing next chunk seamlessly
                return self.step()

        return None

    def process_chunk(self, chunk: AudioChunk) -> Tuple[AudioChunk, VADResult]:
        """Validate, buffer, and process an incoming chunk with VAD and emit typed events.

        Strictly enforces speech-start, audio-chunk, and speech-end event ordering.

        Raises:
            AudioError: ILLEGAL_STATE_TRANSITION if pipeline is not RUNNING.
            AudioError: OUT_OF_ORDER if chunk arrives late or out of sequence.
            AudioError: AUDIO_GAP_DETECTED if a sequence ID gap is found and strict checking is enabled.
        """
        if self._state == LifecycleState.PAUSED:
            raise AudioError(
                AudioErrorCode.ILLEGAL_STATE_TRANSITION,
                "Cannot process chunks while audio pipeline is paused",
            )
        if self._state in (LifecycleState.STOPPED, LifecycleState.CANCELLED):
            raise AudioError(
                AudioErrorCode.ILLEGAL_STATE_TRANSITION,
                f"Cannot process chunks while audio pipeline is {self._state.value}",
            )

        # Check for late chunks (out-of-order)
        if self._last_chunk is not None:
            if (
                chunk.sequence_id <= self._last_chunk.sequence_id
                or chunk.timestamp_s < self._last_chunk.timestamp_s
            ):
                self._late_chunks_detected += 1
                raise AudioError(
                    AudioErrorCode.OUT_OF_ORDER,
                    f"Late chunk received: seq {chunk.sequence_id} <= {self._last_chunk.sequence_id} "
                    f"or timestamp {chunk.timestamp_s} < {self._last_chunk.timestamp_s}",
                )

            # Check for audio gaps
            expected_seq = self._last_chunk.sequence_id + 1
            if chunk.sequence_id > expected_seq:
                self._gaps_detected += 1
                if self.strict_gap_detection:
                    raise AudioError(
                        AudioErrorCode.AUDIO_GAP_DETECTED,
                        f"Audio gap detected: expected sequence_id {expected_seq}, got {chunk.sequence_id}",
                    )

        self._last_chunk = chunk
        self.buffer.push(chunk)
        vad_result = self.vad.process_chunk(chunk)
        self._total_chunks_processed += 1

        # Normalize chunk audio payload for uniform acoustic power
        normalized_chunk = normalize_audio_chunk(chunk)

        # --- Event State Machine: Strictly Ordered Speech Events ---
        if not self._in_speech and vad_result.is_speech:
            # 1. Transition: Silence -> Speech onset
            self._in_speech = True
            self._speech_start_time = chunk.timestamp_s

            # SpeechStartEvent MUST be emitted before the first speech chunk
            start_evt = SpeechStartEvent(
                event_id=self._generate_event_id(),
                session_id=self._session_id,
                correlation_id=self._correlation_id,
                event_type=AudioEventType.SPEECH_START,
                timestamp_s=chunk.timestamp_s,
                sequence_id=self._next_event_seq(),
                speech_start_time_s=chunk.timestamp_s,
            )
            self._emit_event(start_evt)

            chunk_evt = AudioChunkEvent(
                event_id=self._generate_event_id(),
                session_id=self._session_id,
                correlation_id=self._correlation_id,
                event_type=AudioEventType.AUDIO_CHUNK,
                timestamp_s=chunk.timestamp_s,
                sequence_id=self._next_event_seq(),
                chunk=normalized_chunk,
                is_speech=True,
                rms_energy=vad_result.energy,
            )
            self._emit_event(chunk_evt)

        elif self._in_speech and vad_result.is_speech:
            # 2. Continuing speech
            chunk_evt = AudioChunkEvent(
                event_id=self._generate_event_id(),
                session_id=self._session_id,
                correlation_id=self._correlation_id,
                event_type=AudioEventType.AUDIO_CHUNK,
                timestamp_s=chunk.timestamp_s,
                sequence_id=self._next_event_seq(),
                chunk=normalized_chunk,
                is_speech=True,
                rms_energy=vad_result.energy,
            )
            self._emit_event(chunk_evt)

        elif self._in_speech and not vad_result.is_speech:
            # 3. Transition: Speech -> Silence (Speech ended)
            dur = max(0.0, chunk.timestamp_s - self._speech_start_time)
            end_evt = SpeechEndEvent(
                event_id=self._generate_event_id(),
                session_id=self._session_id,
                correlation_id=self._correlation_id,
                event_type=AudioEventType.SPEECH_END,
                timestamp_s=chunk.timestamp_s,
                sequence_id=self._next_event_seq(),
                speech_start_time_s=self._speech_start_time,
                speech_end_time_s=chunk.timestamp_s,
                duration_s=round(dur, 4),
            )
            self._in_speech = False
            self._emit_event(end_evt)

            chunk_evt = AudioChunkEvent(
                event_id=self._generate_event_id(),
                session_id=self._session_id,
                correlation_id=self._correlation_id,
                event_type=AudioEventType.AUDIO_CHUNK,
                timestamp_s=chunk.timestamp_s,
                sequence_id=self._next_event_seq(),
                chunk=normalized_chunk,
                is_speech=False,
                rms_energy=vad_result.energy,
            )
            self._emit_event(chunk_evt)

        else:
            # 4. Continuing silence / non-speech
            chunk_evt = AudioChunkEvent(
                event_id=self._generate_event_id(),
                session_id=self._session_id,
                correlation_id=self._correlation_id,
                event_type=AudioEventType.AUDIO_CHUNK,
                timestamp_s=chunk.timestamp_s,
                sequence_id=self._next_event_seq(),
                chunk=normalized_chunk,
                is_speech=False,
                rms_energy=vad_result.energy,
            )
            self._emit_event(chunk_evt)

        return chunk, vad_result

    def step(self) -> Optional[Tuple[AudioChunk, VADResult]]:
        """Read one chunk from the adapter and process it.

        Handles device-loss recovery safely without crashing.
        Returns None if stream is finished, pipeline is paused, or recovering.
        """
        if self._state == LifecycleState.RECOVERING:
            if self.auto_reconnect:
                if self.recover_device():
                    return self.step()
            return None

        if self._state != LifecycleState.RUNNING:
            return None

        try:
            chunk = self.adapter.read_chunk()
        except AudioError as exc:
            if exc.code == AudioErrorCode.DEVICE_LOST:
                return self._handle_device_loss(exc)
            raise

        if chunk is None:
            return None
        return self.process_chunk(chunk)

    def run_steps(self, max_chunks: Optional[int] = None) -> List[Tuple[AudioChunk, VADResult]]:
        """Process up to max_chunks (or until stream ends) while RUNNING."""
        results: List[Tuple[AudioChunk, VADResult]] = []
        while self.is_running:
            item = self.step()
            if item is None:
                break
            results.append(item)
            if max_chunks is not None and len(results) >= max_chunks:
                break
        return results
