"""Fake microphone: a deterministic audio source for development and tests.

Produces a repeating "silence / tone" pattern (silence first, then a sine tone)
so that later VAD work has both non-speech and speech-like segments to detect.
No hardware, no randomness, no files: same arguments -> identical bytes.
"""

from __future__ import annotations

import math
import sys
import time
from array import array
from typing import Iterator

from .chunker import chunk_pcm
from .schemas import AudioChunk, AudioError, AudioErrorCode, AudioFormat

MAX_DURATION_S = 600.0  # guard against accidentally allocating huge buffers


class MockMicrophone:
    """Emits :class:`AudioChunk` objects like a real microphone would.

    Args:
        fmt:          Output :class:`AudioFormat` (default 16 kHz mono).
        duration_s:   Total stream length in seconds (0 < d <= 600).
        chunk_ms:     Chunk size in milliseconds (must be whole frames).
        frequency_hz: Tone frequency (> 0 and below Nyquist).
        amplitude:    Tone loudness, 0 < a <= 1 (fraction of full scale).
        segment_s:    Length of each alternating silence/tone segment (> 0).
    """

    def __init__(
        self,
        fmt: AudioFormat | None = None,
        duration_s: float = 2.0,
        chunk_ms: int = 20,
        frequency_hz: float = 440.0,
        amplitude: float = 0.5,
        segment_s: float = 0.5,
    ) -> None:
        self.fmt = fmt if fmt is not None else AudioFormat(sample_rate=16000, channels=1)
        if not isinstance(self.fmt, AudioFormat):
            raise AudioError(AudioErrorCode.INVALID_FORMAT, "fmt must be an AudioFormat")
        _check(0 < duration_s <= MAX_DURATION_S, f"duration_s must be in (0, {MAX_DURATION_S}]")
        _check(0 < frequency_hz < self.fmt.sample_rate / 2, "frequency_hz must be in (0, Nyquist)")
        _check(0 < amplitude <= 1, "amplitude must be in (0, 1]")
        _check(segment_s > 0, "segment_s must be > 0")
        self.duration_s = float(duration_s)
        self.chunk_ms = chunk_ms
        self.frequency_hz = float(frequency_hz)
        self.amplitude = float(amplitude)
        self.segment_s = float(segment_s)

    def generate_pcm(self) -> bytes:
        """Build the full PCM buffer (little-endian s16, interleaved channels)."""
        rate = self.fmt.sample_rate
        total_frames = round(self.duration_s * rate)
        if total_frames < 1:
            raise AudioError(AudioErrorCode.INVALID_PARAMETER, "duration too short for 1 frame")
        peak = int(self.amplitude * 32767)
        samples = array("h")
        for n in range(total_frames):
            t = n / rate
            tone_on = int(t / self.segment_s) % 2 == 1
            value = int(peak * math.sin(2 * math.pi * self.frequency_hz * t)) if tone_on else 0
            samples.extend([value] * self.fmt.channels)
        if sys.byteorder == "big":  # keep output little-endian on every platform
            samples.byteswap()
        return samples.tobytes()

    def stream(self, realtime: bool = False) -> Iterator[AudioChunk]:
        """Yield chunks. With ``realtime=True`` sleep one chunk-length between
        chunks (timestamps stay stream-relative, so output is still deterministic)."""
        for chunk in chunk_pcm(self.generate_pcm(), self.fmt, self.chunk_ms):
            yield chunk
            if realtime:
                time.sleep(chunk.duration_s)

    def __iter__(self) -> Iterator[AudioChunk]:
        return self.stream()


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AudioError(AudioErrorCode.INVALID_PARAMETER, message)
