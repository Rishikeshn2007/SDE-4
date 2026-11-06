"""
Voice Activity Detection (VAD) for SDE-4 Speech-to-Text Pipeline.

Provides a reusable, lightweight, energy-based Voice Activity Detector for
determining speech versus silence in raw PCM audio and W1 AudioChunk objects.

Design & Architectural Characteristics:
----------------------------------------
- Energy-based (RMS): Computes root-mean-square amplitude over 16-bit PCM frames.
- Temporal smoothing: Uses configurable minimum speech duration to filter transient
  clicks/noise spikes, and configurable silence hangover duration to avoid premature
  speech chopping between words or sentences.
- Adaptive noise floor: Optionally tracks stationary background noise levels to adjust
  effective speech detection thresholds.
- Zero external dependencies: Uses standard library `array`, `math`, `struct`.
- AudioChunk integration: Works seamlessly with W1 `academia_audio.schemas.AudioChunk`.

Limitations & Contract Boundaries:
----------------------------------
This is a lightweight energy-based VAD, not a deep neural network (e.g., Silero) or
statistical model (e.g., WebRTC Gaussian Mixture VAD). Energy-based VADs can be
sensitive to high-energy non-speech acoustic events (such as loud keyboard taps or
door slams). For high-noise production environments, neural or acoustic model VADs
should be considered as an upstream filter.
"""

from __future__ import annotations

import math
import sys
from array import array
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from academia_audio.schemas import AudioChunk, AudioFormat


class VADState(str, Enum):
    """Voice Activity Detection state."""
    SILENCE = "SILENCE"
    SPEECH = "SPEECH"


@dataclass(frozen=True)
class VADConfig:
    """Configuration parameters for Voice Activity Detection.

    Attributes:
        energy_threshold: RMS amplitude threshold [0.0, 1.0] above which audio
            is considered candidate speech. Default 0.02.
        min_speech_duration_s: Minimum duration of consecutive speech energy
            required to transition state from SILENCE to SPEECH. Default 0.1s.
        min_silence_duration_s: Minimum duration of consecutive silence energy
            required to transition state from SPEECH to SILENCE (hangover). Default 0.4s.
        adaptive_noise: Whether to adaptively track the background noise floor.
        noise_floor_alpha: Smoothing factor for noise floor adaptation (0.0 to 1.0).
    """

    energy_threshold: float = 0.02
    min_speech_duration_s: float = 0.10
    min_silence_duration_s: float = 0.40
    adaptive_noise: bool = True
    noise_floor_alpha: float = 0.05

    def __post_init__(self) -> None:
        if self.energy_threshold < 0.0 or self.energy_threshold > 1.0:
            raise ValueError(f"energy_threshold must be between 0.0 and 1.0, got {self.energy_threshold}")
        if self.min_speech_duration_s < 0.0:
            raise ValueError(f"min_speech_duration_s must be non-negative, got {self.min_speech_duration_s}")
        if self.min_silence_duration_s < 0.0:
            raise ValueError(f"min_silence_duration_s must be non-negative, got {self.min_silence_duration_s}")
        if not (0.0 <= self.noise_floor_alpha <= 1.0):
            raise ValueError(f"noise_floor_alpha must be between 0.0 and 1.0, got {self.noise_floor_alpha}")


@dataclass(frozen=True)
class VADResult:
    """Diagnostic and state output for a processed audio frame or chunk.

    Attributes:
        state: Current smoothed VADState (SILENCE or SPEECH).
        is_speech: Convenience boolean indicating whether speech is active.
        energy: Measured RMS amplitude in [0.0, 1.0].
        speech_duration_s: Accumulated continuous speech duration in seconds.
        silence_duration_s: Accumulated continuous silence duration in seconds.
        transition: State transition tag ("SPEECH_START", "SPEECH_END", or None).
    """

    state: VADState
    is_speech: bool
    energy: float
    speech_duration_s: float
    silence_duration_s: float
    transition: Optional[str] = None


class VoiceActivityDetector:
    """Stateful, reusable Voice Activity Detector for streaming audio."""

    def __init__(self, config: Optional[VADConfig] = None) -> None:
        self.config = config or VADConfig()
        self._state: VADState = VADState.SILENCE
        self._current_speech_run_s: float = 0.0
        self._current_silence_run_s: float = 0.0
        self._noise_floor: float = self.config.energy_threshold * 0.5

    @property
    def current_state(self) -> VADState:
        """Current smoothed VAD state."""
        return self._state

    @property
    def noise_floor(self) -> float:
        """Estimated background noise floor."""
        return self._noise_floor

    def reset(self) -> None:
        """Reset internal temporal state machine and counters."""
        self._state = VADState.SILENCE
        self._current_speech_run_s = 0.0
        self._current_silence_run_s = 0.0
        self._noise_floor = self.config.energy_threshold * 0.5

    @staticmethod
    def compute_rms(pcm_data: bytes, sample_width: int = 2) -> float:
        """Compute normalized RMS energy in [0.0, 1.0] from 16-bit PCM bytes.

        Returns 0.0 for empty byte streams.
        """
        if not pcm_data:
            return 0.0

        if sample_width != 2:
            raise ValueError(f"Only 16-bit PCM (sample_width=2) is supported, got {sample_width}")

        if len(pcm_data) % 2 != 0:
            raise ValueError(f"PCM byte buffer length ({len(pcm_data)}) must be a multiple of 2")

        samples = array("h")
        samples.frombytes(pcm_data)
        if sys.byteorder == "big":
            samples.byteswap()

        if not samples:
            return 0.0

        mean_sq = sum(s * s for s in samples) / len(samples)
        return math.sqrt(mean_sq) / 32768.0

    def process_chunk(
        self,
        chunk: Union[AudioChunk, bytes],
        sample_rate: Optional[int] = None,
        channels: int = 1,
        sample_width: int = 2,
    ) -> VADResult:
        """Process an AudioChunk or raw PCM bytes through the VAD state machine.

        Args:
            chunk: AudioChunk instance or raw PCM bytes.
            sample_rate: Sampling rate in Hz (defaults to 16000 or chunk's format rate).
            channels: Channel count (defaults to 1 or chunk's format channels).
            sample_width: Bytes per sample (must be 2).

        Returns:
            VADResult with current speech decision, RMS energy, and transitions.
        """
        if isinstance(chunk, AudioChunk):
            pcm_bytes = chunk.data
            sr = chunk.format.sample_rate
            ch = chunk.format.channels
            sw = chunk.format.sample_width
            duration_s = chunk.duration_s
        elif isinstance(chunk, (bytes, bytearray)):
            pcm_bytes = bytes(chunk)
            sr = sample_rate or 16000
            ch = channels
            sw = sample_width
            frame_size = ch * sw
            if frame_size <= 0:
                raise ValueError("Frame size must be positive")
            duration_s = (len(pcm_bytes) / frame_size) / sr if len(pcm_bytes) > 0 else 0.0
        else:
            raise TypeError(f"Expected AudioChunk or bytes, got {type(chunk).__name__}")

        # Compute energy
        energy = self.compute_rms(pcm_bytes, sample_width=sw)

        # Dynamic threshold considering adaptive noise floor
        effective_threshold = self.config.energy_threshold
        if self.config.adaptive_noise:
            # Shift threshold above current background noise
            effective_threshold = max(self.config.energy_threshold, self._noise_floor * 1.5)

        is_instant_speech = energy >= effective_threshold

        transition: Optional[str] = None

        if is_instant_speech:
            self._current_speech_run_s += duration_s
            self._current_silence_run_s = 0.0

            if self._state == VADState.SILENCE:
                # Check if speech duration requirement is satisfied
                if self._current_speech_run_s >= self.config.min_speech_duration_s:
                    self._state = VADState.SPEECH
                    transition = "SPEECH_START"
        else:
            self._current_silence_run_s += duration_s
            self._current_speech_run_s = 0.0

            # Update noise floor adaptively during silence
            if self.config.adaptive_noise and energy > 0.0:
                self._noise_floor = (
                    (1.0 - self.config.noise_floor_alpha) * self._noise_floor
                    + self.config.noise_floor_alpha * energy
                )

            if self._state == VADState.SPEECH:
                # Check if silence hangover duration requirement is satisfied
                if self._current_silence_run_s >= self.config.min_silence_duration_s:
                    self._state = VADState.SILENCE
                    transition = "SPEECH_END"

        return VADResult(
            state=self._state,
            is_speech=(self._state == VADState.SPEECH),
            energy=round(energy, 5),
            speech_duration_s=round(self._current_speech_run_s, 4),
            silence_duration_s=round(self._current_silence_run_s, 4),
            transition=transition,
        )


__all__ = [
    "VADState",
    "VADConfig",
    "VADResult",
    "VoiceActivityDetector",
]

