"""Bounded audio buffer with backpressure and dropped-chunk tracking.

Enforces a configurable maximum capacity so memory cannot grow unbounded
during high-load spikes or consumer stalls.
"""

from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Deque, Iterator, Optional

from .schemas import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    _is_int,
)


class OverflowStrategy(str, Enum):
    """Action taken when pushing a chunk into an already-full buffer."""

    DROP_OLDEST = "drop_oldest"  # Discard oldest chunk to prioritize low latency (default for live audio)
    DROP_NEWEST = "drop_newest"  # Discard incoming chunk to protect existing backlog
    REJECT = "reject"            # Raise an AudioError with BUFFER_OVERFLOW code


class BoundedAudioBuffer:
    """Fixed-capacity buffer for AudioChunks with dropped chunk accounting.

    Parameters:
        capacity:          Maximum number of AudioChunks allowed in the buffer (> 0).
        overflow_strategy: Policy applied when capacity is exceeded.
    """

    def __init__(
        self,
        capacity: int = 100,
        overflow_strategy: OverflowStrategy = OverflowStrategy.DROP_OLDEST,
    ) -> None:
        if not _is_int(capacity) or capacity <= 0:
            raise AudioError(
                AudioErrorCode.INVALID_PARAMETER,
                f"capacity must be an int > 0, got {capacity!r}",
            )
        self.capacity: int = capacity
        self.overflow_strategy: OverflowStrategy = overflow_strategy
        self._queue: Deque[AudioChunk] = deque()
        self._dropped_chunks: int = 0
        self._total_pushed: int = 0
        self._total_popped: int = 0

    @property
    def size(self) -> int:
        """Current number of chunks in the buffer."""
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        """True if the buffer contains zero chunks."""
        return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        """True if current size has reached or exceeded maximum capacity."""
        return len(self._queue) >= self.capacity

    @property
    def dropped_chunks(self) -> int:
        """Total count of chunks dropped due to buffer capacity overflow."""
        return self._dropped_chunks

    @property
    def total_pushed(self) -> int:
        """Total number of chunks successfully accepted into the buffer."""
        return self._total_pushed

    @property
    def total_popped(self) -> int:
        """Total number of chunks retrieved from the buffer."""
        return self._total_popped

    @property
    def total_bytes(self) -> int:
        """Sum of data sizes (bytes) currently stored in the buffer."""
        return sum(c.size_bytes for c in self._queue)

    @property
    def total_duration_s(self) -> float:
        """Sum of duration (seconds) currently stored in the buffer."""
        return sum(c.duration_s for c in self._queue)

    def push(self, chunk: AudioChunk) -> bool:
        """Add a chunk to the buffer.

        If the buffer is full, applies configured backpressure strategy and
        increments the dropped chunk counter.

        Returns:
            True if chunk was added without dropping.
            False if an overflow occurred and a chunk was dropped.

        Raises:
            AudioError: INVALID_DATA_TYPE if chunk is not an AudioChunk.
            AudioError: BUFFER_OVERFLOW if overflow_strategy is REJECT and buffer is full.
        """
        if not isinstance(chunk, AudioChunk):
            raise AudioError(
                AudioErrorCode.INVALID_DATA_TYPE,
                f"chunk must be an AudioChunk instance, got {type(chunk).__name__}",
            )

        if len(self._queue) >= self.capacity:
            self._dropped_chunks += 1
            if self.overflow_strategy == OverflowStrategy.DROP_OLDEST:
                self._queue.popleft()
                self._queue.append(chunk)
                self._total_pushed += 1
                return False
            elif self.overflow_strategy == OverflowStrategy.DROP_NEWEST:
                # Discard the incoming chunk
                return False
            elif self.overflow_strategy == OverflowStrategy.REJECT:
                raise AudioError(
                    AudioErrorCode.BUFFER_OVERFLOW,
                    f"Buffer overflow: capacity of {self.capacity} chunks exceeded",
                )

        self._queue.append(chunk)
        self._total_pushed += 1
        return True

    def pop(self) -> Optional[AudioChunk]:
        """Remove and return the oldest chunk, or None if buffer is empty."""
        if not self._queue:
            return None
        self._total_popped += 1
        return self._queue.popleft()

    def peek(self) -> Optional[AudioChunk]:
        """Return the oldest chunk without removing it, or None if empty."""
        if not self._queue:
            return None
        return self._queue[0]

    def release(self) -> None:
        """Release and discard all chunks currently held in the buffer."""
        self._queue.clear()

    def clear(self) -> None:
        """Alias for :meth:`release`."""
        self.release()

    def __len__(self) -> int:
        return len(self._queue)

    def __iter__(self) -> Iterator[AudioChunk]:
        """Iterate over currently buffered chunks without removing them."""
        return iter(list(self._queue))
