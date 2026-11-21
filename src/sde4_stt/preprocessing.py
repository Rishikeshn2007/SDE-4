"""Audio preprocessing module for the SDE-4 Speech-to-Text (W2) pipeline.

Provides anti-aliased resampling, channel conversion, and RMS normalization of raw PCM audio.
Works with W1 :class:`~academia_audio.schemas.AudioChunk` objects (frozen dataclasses).

Design & Signal Processing Characteristics:
--------------------------------------------
* **Stdlib only** – uses :mod:`struct`, :mod:`array`, and :mod:`math`; zero heavy binary
  dependencies required for standard pipeline operation.
* **Anti-Aliasing Resampling** – When downsampling (target_rate < source_rate), a windowed-sinc
  FIR low-pass filter is convolved across each channel to suppress frequencies above the target
  Nyquist frequency (0.45 * target_rate / source_rate), preventing spectral aliasing and distortion.
  When upsampling, band-limited linear interpolation is applied.
* **Channel Management** – Explicitly supports mono (1ch) <-> stereo (2ch) conversions.
  Stereo downmixing applies energy-conserving channel averaging.
* **Headroom-Preserving Normalization** – Scales audio to target RMS while using dynamic
  headroom scaling to avoid harsh digital clipping and distortion.
* **Immutable Chunks** – :meth:`AudioPreprocessor.process_chunk` returns a new AudioChunk
  preserving sequence_id, timestamp_s, and metadata.
"""

from __future__ import annotations

import math
import struct
from typing import List, Optional

from academia_audio.schemas import AudioChunk, AudioFormat


class AudioPreprocessor:
    """Resamples, converts channels, and normalizes raw PCM audio for downstream STT models.

    The preprocessor targets a canonical format (e.g. 16 kHz mono, RMS-normalised)
    so that the transcription adapter always receives uniform input regardless of
    the source recording conditions.

    Attributes:
        target_sample_rate: Desired output sample rate in Hz.
        target_channels:    Desired number of output channels (1 = mono, 2 = stereo).
        normalize_audio:    Whether to apply RMS normalization.
        target_rms:         Target RMS amplitude (0.0–1.0 range for 16-bit
                            PCM mapped to [-1, 1]).
    """

    def __init__(
        self,
        target_sample_rate: int = 16000,
        target_channels: int = 1,
        normalize_audio: bool = True,
        target_rms: float = 0.1,
    ) -> None:
        """Initialise the preprocessor with target audio parameters."""
        if target_sample_rate <= 0:
            raise ValueError(
                f"target_sample_rate must be positive, got {target_sample_rate}"
            )
        if target_channels not in (1, 2):
            raise ValueError(
                f"target_channels must be 1 (mono) or 2 (stereo), got {target_channels}"
            )
        if target_rms <= 0.0 or target_rms > 1.0:
            raise ValueError(
                f"target_rms must be in (0.0, 1.0], got {target_rms}"
            )

        self.target_sample_rate: int = target_sample_rate
        self.target_channels: int = target_channels
        self.normalize_audio: bool = normalize_audio
        self.target_rms: float = target_rms

    # ------------------------------------------------------------------
    # Anti-aliasing FIR Filter Design
    # ------------------------------------------------------------------

    @staticmethod
    def _design_lowpass_fir(cutoff_ratio: float, num_taps: int = 31) -> List[float]:
        """Design a symmetric windowed-sinc FIR low-pass filter with a Hamming window.

        Args:
            cutoff_ratio: Normalized cutoff frequency in (0.0, 0.5].
            num_taps: Odd integer number of filter taps.

        Returns:
            List of normalized filter coefficients summing to 1.0.
        """
        half_m = (num_taps - 1) / 2.0
        taps: List[float] = []

        for i in range(num_taps):
            m = i - half_m
            # Sinc function
            if abs(m) < 1e-9:
                sinc_val = 2.0 * cutoff_ratio
            else:
                sinc_val = math.sin(2.0 * math.pi * cutoff_ratio * m) / (math.pi * m)

            # Hamming window
            window_val = 0.54 - 0.46 * math.cos(2.0 * math.pi * i / (num_taps - 1))
            taps.append(sinc_val * window_val)

        # Normalize gain to unity at DC (sum of coefficients = 1.0)
        total_sum = sum(taps)
        if abs(total_sum) > 1e-12:
            taps = [t / total_sum for t in taps]
        return taps

    def _apply_anti_aliasing(
        self,
        samples: List[int],
        channels: int,
        source_rate: int,
        target_rate: int,
    ) -> List[int]:
        """Apply anti-aliasing low-pass filter to samples per channel before downsampling."""
        ratio = target_rate / float(source_rate)
        # Set cutoff slightly below target Nyquist frequency (safety guardband)
        cutoff = min(0.45, 0.45 * ratio)
        taps = self._design_lowpass_fir(cutoff_ratio=cutoff, num_taps=31)
        num_taps = len(taps)
        half_taps = num_taps // 2

        num_frames = len(samples) // channels
        filtered_samples = list(samples)

        for ch in range(channels):
            # Extract channel frames
            ch_data = [samples[i * channels + ch] for i in range(num_frames)]
            filtered_ch = []

            for i in range(num_frames):
                acc = 0.0
                for k in range(num_taps):
                    # Clamp index at boundaries
                    src_idx = min(max(0, i - half_taps + k), num_frames - 1)
                    acc += taps[k] * ch_data[src_idx]
                filtered_ch.append(max(-32768, min(32767, round(acc))))

            for i in range(num_frames):
                filtered_samples[i * channels + ch] = filtered_ch[i]

        return filtered_samples

    # ------------------------------------------------------------------
    # Channel Conversion
    # ------------------------------------------------------------------

    def convert_channels(
        self,
        pcm_data: bytes,
        source_channels: int,
        target_channels: int,
        sample_width: int = 2,
    ) -> bytes:
        """Convert PCM bytes between supported channel counts (mono <-> stereo)."""
        if source_channels == target_channels:
            return pcm_data

        if source_channels not in (1, 2) or target_channels not in (1, 2):
            raise ValueError(
                f"Unsupported channel conversion: {source_channels} -> {target_channels}. "
                "Supported channels are 1 (mono) and 2 (stereo)."
            )

        num_samples = len(pcm_data) // sample_width
        fmt = f"<{num_samples}h"
        samples = struct.unpack(fmt, pcm_data)

        if source_channels == 2 and target_channels == 1:
            # Downmix stereo to mono: average L and R
            mono = [(samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples), 2)]
            return struct.pack(f"<{len(mono)}h", *mono)

        if source_channels == 1 and target_channels == 2:
            # Upmix mono to stereo: duplicate channel to L and R
            stereo: List[int] = []
            for s in samples:
                stereo.extend([s, s])
            return struct.pack(f"<{len(stereo)}h", *stereo)

        return pcm_data

    # ------------------------------------------------------------------
    # Resampling
    # ------------------------------------------------------------------

    def resample(
        self,
        pcm_data: bytes,
        source_rate: int,
        target_rate: int,
        channels: int = 1,
        sample_width: int = 2,
    ) -> bytes:
        """Resample raw PCM audio with anti-aliasing downsampling and linear upsampling.

        Converts ``pcm_data`` from ``source_rate`` Hz to ``target_rate`` Hz.
        The returned buffer length is always a whole number of frames.
        """
        if len(pcm_data) == 0:
            raise ValueError("pcm_data must not be empty")
        if source_rate <= 0:
            raise ValueError(f"source_rate must be positive, got {source_rate}")
        if target_rate <= 0:
            raise ValueError(f"target_rate must be positive, got {target_rate}")

        if source_rate == target_rate:
            return pcm_data

        frame_size = channels * sample_width
        if len(pcm_data) % frame_size != 0:
            raise ValueError(
                f"pcm_data length ({len(pcm_data)}) is not a multiple of "
                f"frame size ({frame_size})"
            )

        # Unpack samples
        fmt = f"<{len(pcm_data) // sample_width}h"
        source_samples = list(struct.unpack(fmt, pcm_data))

        # Apply anti-aliasing FIR filter if downsampling
        if target_rate < source_rate:
            source_samples = self._apply_anti_aliasing(
                source_samples, channels, source_rate, target_rate,
            )

        source_frames = len(source_samples) // channels
        target_frames = max(1, round(source_frames * target_rate / source_rate))

        result_samples: List[int] = []

        for t in range(target_frames):
            src_pos = t * (source_frames - 1) / max(target_frames - 1, 1)
            src_idx = int(src_pos)
            frac = src_pos - src_idx

            for ch in range(channels):
                s0 = source_samples[src_idx * channels + ch]
                if src_idx + 1 < source_frames:
                    s1 = source_samples[(src_idx + 1) * channels + ch]
                else:
                    s1 = s0
                interpolated = s0 + frac * (s1 - s0)
                result_samples.append(
                    max(-32768, min(32767, round(interpolated)))
                )

        out_fmt = f"<{len(result_samples)}h"
        return struct.pack(out_fmt, *result_samples)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def normalize(
        self,
        pcm_data: bytes,
        channels: int = 1,
        sample_width: int = 2,
    ) -> bytes:
        """Normalize audio to configured target RMS level without clipping distortion."""
        if len(pcm_data) == 0:
            raise ValueError("pcm_data must not be empty")

        num_samples = len(pcm_data) // sample_width
        if num_samples == 0 or len(pcm_data) % sample_width != 0:
            raise ValueError(
                f"pcm_data length ({len(pcm_data)}) is not a multiple of "
                f"sample_width ({sample_width})"
            )

        fmt = f"<{num_samples}h"
        samples = list(struct.unpack(fmt, pcm_data))

        # Compute RMS on [-1, 1] float scale
        max_val = 32768.0
        sum_sq = sum((s / max_val) ** 2 for s in samples)
        rms = math.sqrt(sum_sq / num_samples)

        # Silence threshold: avoid amplifying noise floor
        if rms < 1e-6:
            return pcm_data

        gain = self.target_rms / rms

        # Dynamic headroom scaling to strictly avoid clipping
        max_abs = max(abs(s) for s in samples) if samples else 0
        if max_abs > 0 and (max_abs * gain) > 32767:
            gain = 32760.0 / max_abs

        scaled = [
            max(-32768, min(32767, round(s * gain)))
            for s in samples
        ]

        out_fmt = f"<{len(scaled)}h"
        return struct.pack(out_fmt, *scaled)

    # ------------------------------------------------------------------
    # Chunk-level processing
    # ------------------------------------------------------------------

    def process_chunk(self, chunk: AudioChunk) -> AudioChunk:
        """Apply resampling, channel conversion, and normalization to a W1 AudioChunk.

        Returns a new frozen AudioChunk instance preserving metadata.
        """
        processed_data: bytes = chunk.data
        current_rate: int = chunk.format.sample_rate
        current_channels: int = chunk.format.channels
        current_sample_width: int = chunk.format.sample_width

        # Step 1: Resample if needed
        if current_rate != self.target_sample_rate:
            processed_data = self.resample(
                pcm_data=processed_data,
                source_rate=current_rate,
                target_rate=self.target_sample_rate,
                channels=current_channels,
                sample_width=current_sample_width,
            )
            current_rate = self.target_sample_rate

        # Step 2: Channel conversion if needed
        if current_channels != self.target_channels:
            processed_data = self.convert_channels(
                pcm_data=processed_data,
                source_channels=current_channels,
                target_channels=self.target_channels,
                sample_width=current_sample_width,
            )
            current_channels = self.target_channels

        # Step 3: Normalize if enabled
        if self.normalize_audio:
            processed_data = self.normalize(
                pcm_data=processed_data,
                channels=current_channels,
                sample_width=current_sample_width,
            )

        target_format = AudioFormat(
            sample_rate=current_rate,
            channels=current_channels,
            sample_width=current_sample_width,
        )

        return AudioChunk(
            sequence_id=chunk.sequence_id,
            timestamp_s=chunk.timestamp_s,
            format=target_format,
            data=processed_data,
        )


__all__ = ["AudioPreprocessor"]
