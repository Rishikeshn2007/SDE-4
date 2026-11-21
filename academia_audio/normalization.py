"""Audio normalization utilities for the Academia AI Voice Bot (Week 3).

Provides deterministic peak scaling and PCM normalization to guarantee
standardized acoustic levels across chunks prior to transcription ingestion.
"""

from __future__ import annotations

import sys
from array import array
from typing import Optional

from .schemas import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    crc32,
)


def compute_peak_amplitude(data: bytes) -> float:
    """Calculate the normalized absolute peak amplitude of 16-bit signed PCM data.

    Returns:
        float in [0.0, 1.0] representing peak acoustic amplitude relative to full scale.
    """
    if len(data) == 0:
        return 0.0
    samples = array("h")
    samples.frombytes(data)
    if sys.byteorder == "big":
        samples.byteswap()
    if len(samples) == 0:
        return 0.0
    max_abs = max(abs(s) for s in samples)
    return max_abs / 32768.0


def normalize_pcm_bytes(data: bytes, target_peak: float = 0.95) -> bytes:
    """Scale 16-bit signed PCM linear audio data to target peak amplitude.

    Args:
        data:        Raw 16-bit PCM bytes (signed little-endian).
        target_peak: Target peak amplitude in range (0.0, 1.0]. Default is 0.95.

    Returns:
        Normalized bytes. If data is silence (peak == 0), returns input bytes unmodified.
    """
    if len(data) == 0:
        return data
    if not (0.0 < target_peak <= 1.0):
        raise AudioError(
            AudioErrorCode.INVALID_PARAMETER,
            f"target_peak must be in (0.0, 1.0], got {target_peak!r}",
        )

    samples = array("h")
    samples.frombytes(data)
    if sys.byteorder == "big":
        samples.byteswap()

    if len(samples) == 0:
        return data

    current_peak = max(abs(s) for s in samples)
    if current_peak == 0:
        return data

    target_val = int(target_peak * 32767)
    if current_peak == target_val:
        return data

    gain = target_val / float(current_peak)
    normalized_samples = array("h")
    for s in samples:
        val = int(s * gain)
        # Clamp to 16-bit signed range
        if val > 32767:
            val = 32767
        elif val < -32768:
            val = -32768
        normalized_samples.append(val)

    if sys.byteorder == "big":
        normalized_samples.byteswap()

    return normalized_samples.tobytes()


def normalize_audio_chunk(
    chunk: AudioChunk,
    target_peak: float = 0.95,
) -> AudioChunk:
    """Produce a normalized copy of an :class:`AudioChunk`.

    Normalizes the chunk's PCM payload while preserving sequence metadata,
    timestamps, and audio format. Recomputes CRC32 checksum if present.

    Args:
        chunk:       Source :class:`AudioChunk`.
        target_peak: Target peak amplitude fraction in (0.0, 1.0].

    Returns:
        New immutable :class:`AudioChunk` containing normalized audio.
    """
    if not isinstance(chunk, AudioChunk):
        raise AudioError(
            AudioErrorCode.INVALID_DATA_TYPE,
            f"chunk must be an AudioChunk instance, got {type(chunk).__name__}",
        )

    norm_data = normalize_pcm_bytes(chunk.data, target_peak=target_peak)
    norm_checksum = crc32(norm_data) if chunk.checksum is not None else None

    return AudioChunk(
        sequence_id=chunk.sequence_id,
        timestamp_s=chunk.timestamp_s,
        format=chunk.format,
        data=norm_data,
        checksum=norm_checksum,
    )
