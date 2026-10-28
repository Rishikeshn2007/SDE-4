"""Deterministic audio chunker: raw PCM bytes -> ordered AudioChunks."""

from __future__ import annotations

from typing import Iterator

from .schemas import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
    _is_int,
    crc32,
)


def frames_per_chunk(fmt: AudioFormat, chunk_ms: int) -> int:
    """Frames in one ``chunk_ms`` chunk. ``chunk_ms`` must map to whole frames."""
    if not _is_int(chunk_ms) or chunk_ms <= 0:
        raise AudioError(
            AudioErrorCode.INVALID_PARAMETER, f"chunk_ms must be an int > 0, got {chunk_ms!r}"
        )
    if (fmt.sample_rate * chunk_ms) % 1000 != 0:
        raise AudioError(
            AudioErrorCode.INVALID_PARAMETER,
            f"chunk_ms={chunk_ms} is not a whole number of frames at {fmt.sample_rate} Hz",
        )
    return fmt.sample_rate * chunk_ms // 1000


def chunk_pcm(
    pcm: bytes,
    fmt: AudioFormat,
    chunk_ms: int = 20,
    start_sequence_id: int = 0,
) -> Iterator[AudioChunk]:
    """Split ``pcm`` into fixed-size chunks (last one may be shorter).

    Deterministic: the same ``pcm`` + arguments always yield identical chunks.
    Timestamps are computed from the integer frame index (``index / sample_rate``)
    so there is no accumulated floating-point drift.

    Arguments are validated immediately (not on first ``next()``).

    Raises:
        AudioError: empty input, misaligned/corrupt input, bad parameters.
    """
    if not isinstance(fmt, AudioFormat):
        raise AudioError(AudioErrorCode.INVALID_FORMAT, "fmt must be an AudioFormat")
    if not isinstance(pcm, bytes):
        raise AudioError(
            AudioErrorCode.INVALID_DATA_TYPE, f"pcm must be bytes, got {type(pcm).__name__}"
        )
    if len(pcm) == 0:
        raise AudioError(AudioErrorCode.EMPTY_CHUNK, "cannot chunk empty audio")
    if len(pcm) % fmt.frame_size != 0:
        raise AudioError(
            AudioErrorCode.CORRUPT_CHUNK,
            f"pcm length {len(pcm)} is not a multiple of the frame size {fmt.frame_size}",
        )
    if not _is_int(start_sequence_id) or start_sequence_id < 0:
        raise AudioError(
            AudioErrorCode.INVALID_SEQUENCE_ID,
            f"start_sequence_id must be an int >= 0, got {start_sequence_id!r}",
        )
    step = frames_per_chunk(fmt, chunk_ms)
    return _iter_chunks(pcm, fmt, step, start_sequence_id)


def _iter_chunks(pcm: bytes, fmt: AudioFormat, step: int, start_seq: int) -> Iterator[AudioChunk]:
    total_frames = len(pcm) // fmt.frame_size
    for i, first in enumerate(range(0, total_frames, step)):
        last = min(first + step, total_frames)
        data = pcm[first * fmt.frame_size : last * fmt.frame_size]
        yield AudioChunk(
            sequence_id=start_seq + i,
            timestamp_s=first / fmt.sample_rate,
            format=fmt,
            data=data,
            checksum=crc32(data),
        )
