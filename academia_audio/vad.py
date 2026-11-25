"""Voice Activity Detection (VAD) interface and deterministic mock implementation.

Analyzes raw AudioChunks to classify audio into speech vs. non-speech,
with configurable energy thresholds and minimum speech duration constraints.
"""

from __future__ import annotations

import math
import sys
from abc import ABC, abstractmethod
from array import array
from dataclasses import dataclass
from typing import Optional

from .schemas import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
)


@dataclass(frozen=True)
class VADResult:
    """Output metadata produced by evaluating an :class:`AudioChunk`.

    Fields:
        is_speech:         True if voice activity is detected.
        confidence:        Estimated probability that voice is present (0.0 to 1.0).
        energy:            Normalized root-mean-square (RMS) energy level (0.0 to 1.0).
        sequence_id:       Sequence ID of the processed chunk.
        timestamp_s:       Timestamp of the processed chunk.
        speech_duration_s: Continuous detected speech duration so far in seconds.
    """

    is_speech: bool
    confidence: float
    energy: float
    sequence_id: int
    timestamp_s: float
    speech_duration_s: float


def compute_rms(data: bytes) -> float:
    """Calculate the normalized RMS amplitude of 16-bit signed PCM bytes.

    Returns:
        float in [0.0, 1.0] representing acoustic power.
    """
    if len(data) == 0:
        return 0.0
    samples = array("h")
    samples.frombytes(data)
    if sys.byteorder == "big":
        samples.byteswap()
    if len(samples) == 0:
        return 0.0
    sum_squares = sum(s * s for s in samples)
    return math.sqrt(sum_squares / len(samples)) / 32768.0


class BaseVAD(ABC):
    """Abstract interface for Voice Activity Detectors."""

    @abstractmethod
    def process_chunk(self, chunk: AudioChunk) -> VADResult:
        """Analyze an AudioChunk and determine whether it contains active speech."""

    @abstractmethod
    def reset(self) -> None:
        """Reset internal accumulator state between utterances or sessions."""


class MockVAD(BaseVAD):
    """Deterministic, energy-based VAD for testing and offline audio pipelines.

    Uses an RMS threshold and requires speech energy to persist for at least
    ``min_speech_duration_ms`` before asserting voice activity. This prevents
    brief acoustic transients, clicks, or low-level background noise from triggering
    false positives.

    Args:
        energy_threshold:       RMS level (0.0 < e <= 1.0) above which a frame
                                is considered candidate speech. Default is 0.05.
        min_speech_duration_ms: Minimum consecutive duration of candidate speech
                                (in milliseconds) before `is_speech` becomes True.
        speech_pad_ms:          Hangover duration (in milliseconds) to keep speech
                                active during micro-pauses within an utterance.
    """

    def __init__(
        self,
        energy_threshold: float = 0.05,
        min_speech_duration_ms: float = 60.0,
        speech_pad_ms: float = 20.0,
    ) -> None:
        if (
            isinstance(energy_threshold, bool)
            or not isinstance(energy_threshold, (int, float))
            or not (0.0 < energy_threshold <= 1.0)
        ):
            raise AudioError(
                AudioErrorCode.INVALID_PARAMETER,
                f"energy_threshold must be a number in (0.0, 1.0], got {energy_threshold!r}",
            )
        if (
            isinstance(min_speech_duration_ms, bool)
            or not isinstance(min_speech_duration_ms, (int, float))
            or min_speech_duration_ms < 0.0
        ):
            raise AudioError(
                AudioErrorCode.INVALID_PARAMETER,
                f"min_speech_duration_ms must be >= 0.0, got {min_speech_duration_ms!r}",
            )
        if (
            isinstance(speech_pad_ms, bool)
            or not isinstance(speech_pad_ms, (int, float))
            or speech_pad_ms < 0.0
        ):
            raise AudioError(
                AudioErrorCode.INVALID_PARAMETER,
                f"speech_pad_ms must be >= 0.0, got {speech_pad_ms!r}",
            )

        self.energy_threshold: float = float(energy_threshold)
        self.min_speech_duration_ms: float = float(min_speech_duration_ms)
        self.speech_pad_ms: float = float(speech_pad_ms)

        self._consecutive_speech_ms: float = 0.0
        self._hangover_ms: float = 0.0
        self._in_speech: bool = False

    def reset(self) -> None:
        self._consecutive_speech_ms = 0.0
        self._hangover_ms = 0.0
        self._in_speech = False

    def process_chunk(self, chunk: AudioChunk) -> VADResult:
        if not isinstance(chunk, AudioChunk):
            raise AudioError(
                AudioErrorCode.INVALID_DATA_TYPE,
                f"chunk must be an AudioChunk instance, got {type(chunk).__name__}",
            )

        energy = compute_rms(chunk.data)
        chunk_ms = chunk.duration_s * 1000.0

        if energy >= self.energy_threshold:
            self._consecutive_speech_ms += chunk_ms
            self._hangover_ms = self.speech_pad_ms
            if self._consecutive_speech_ms >= self.min_speech_duration_ms:
                self._in_speech = True
        else:
            if self._in_speech and self._hangover_ms > 0.0:
                self._hangover_ms -= chunk_ms
                self._consecutive_speech_ms += chunk_ms
            else:
                self._consecutive_speech_ms = 0.0
                self._in_speech = False

        if self._in_speech:
            confidence = min(1.0, 0.5 + 0.5 * (energy / max(self.energy_threshold * 2.0, 1e-6)))
            speech_duration_s = self._consecutive_speech_ms / 1000.0
        else:
            confidence = max(0.0, min(0.49, 0.5 * (energy / max(self.energy_threshold, 1e-6))))
            speech_duration_s = 0.0

        return VADResult(
            is_speech=self._in_speech,
            confidence=round(confidence, 4),
            energy=round(energy, 6),
            sequence_id=chunk.sequence_id,
            timestamp_s=chunk.timestamp_s,
            speech_duration_s=round(speech_duration_s, 4),
        )
