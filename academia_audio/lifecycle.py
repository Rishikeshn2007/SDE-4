"""Audio pipeline lifecycle controller and state machine (Week 2 - Audio & VAD).

Coordinates the DeviceAdapter, BoundedAudioBuffer, and VAD components while
strictly enforcing valid state transitions (start, pause, resume, stop) and
guaranteeing proper resource cleanup upon termination.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple

from .buffer import BoundedAudioBuffer
from .device import DeviceAdapter, MockDeviceAdapter
from .schemas import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
)
from .vad import BaseVAD, MockVAD, VADResult


class LifecycleState(str, Enum):
    """Execution state of the audio pipeline."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class AudioPipeline:
    """Manages audio capture lifecycle, buffering, VAD, and order verification.

    Enforces the following state machine:
        * STOPPED -> RUNNING via :meth:`start`
        * RUNNING -> PAUSED via :meth:`pause`
        * PAUSED  -> RUNNING via :meth:`resume`
        * RUNNING -> STOPPED via :meth:`stop`
        * PAUSED  -> STOPPED via :meth:`stop`

    All other transitions are considered illegal and raise :class:`AudioError`
    with code ``AudioErrorCode.ILLEGAL_STATE_TRANSITION``.

    Parameters:
        adapter:               Audio input adapter (defaults to :class:`MockDeviceAdapter`).
        buffer:                Bounded buffer (defaults to capacity=50).
        vad:                   Voice Activity Detector (defaults to :class:`MockVAD`).
        fmt:                   Target audio format (defaults to 16 kHz mono).
        strict_gap_detection:  If True, raises an AudioError when a sequence ID gap is detected.
    """

    def __init__(
        self,
        adapter: Optional[DeviceAdapter] = None,
        buffer: Optional[BoundedAudioBuffer] = None,
        vad: Optional[BaseVAD] = None,
        fmt: Optional[AudioFormat] = None,
        strict_gap_detection: bool = False,
    ) -> None:
        self.fmt: AudioFormat = fmt if fmt is not None else AudioFormat(16000, 1)
        self.adapter: DeviceAdapter = adapter if adapter is not None else MockDeviceAdapter()
        self.buffer: BoundedAudioBuffer = buffer if buffer is not None else BoundedAudioBuffer(capacity=50)
        self.vad: BaseVAD = vad if vad is not None else MockVAD()
        self.strict_gap_detection: bool = strict_gap_detection

        self._state: LifecycleState = LifecycleState.STOPPED
        self._last_chunk: Optional[AudioChunk] = None
        self._gaps_detected: int = 0
        self._late_chunks_detected: int = 0
        self._total_chunks_processed: int = 0

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
        return self._state == LifecycleState.STOPPED

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

    def start(self) -> None:
        """Transition from STOPPED to RUNNING, opening the audio adapter.

        Raises:
            AudioError: ILLEGAL_STATE_TRANSITION if not in STOPPED state.
            AudioError: PERMISSION_DENIED or DEVICE_UNSUPPORTED if adapter fails.
        """
        if self._state != LifecycleState.STOPPED:
            raise AudioError(
                AudioErrorCode.ILLEGAL_STATE_TRANSITION,
                f"Cannot start audio pipeline: current state is '{self._state.value}' (expected 'stopped')",
            )

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
        """Transition from RUNNING or PAUSED to STOPPED.

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
            self.adapter.close()
        finally:
            # Acceptance Criterion: Stop releases the buffer.
            self.buffer.release()
            self.vad.reset()
            self._state = LifecycleState.STOPPED
            self._last_chunk = None

    def process_chunk(self, chunk: AudioChunk) -> Tuple[AudioChunk, VADResult]:
        """Validate, buffer, and process an incoming chunk with VAD.

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
        if self._state == LifecycleState.STOPPED:
            raise AudioError(
                AudioErrorCode.ILLEGAL_STATE_TRANSITION,
                "Cannot process chunks while audio pipeline is stopped",
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
        return chunk, vad_result

    def step(self) -> Optional[Tuple[AudioChunk, VADResult]]:
        """Read one chunk from the adapter and process it.

        Returns None if stream is finished or pipeline is paused.
        """
        if self._state != LifecycleState.RUNNING:
            return None
        chunk = self.adapter.read_chunk()
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
