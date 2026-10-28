"""Academia AI Voice Bot - W1 audio foundation (schemas, mock mic, chunker)."""

from .chunker import chunk_pcm
from .mock_source import MockMicrophone
from .schemas import (
    AudioChunk,
    AudioError,
    AudioErrorCode,
    AudioFormat,
    assert_stream_order,
)

__all__ = [
    "AudioChunk",
    "AudioError",
    "AudioErrorCode",
    "AudioFormat",
    "MockMicrophone",
    "assert_stream_order",
    "chunk_pcm",
]
