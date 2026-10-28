"""Manual test: stream your REAL laptop microphone into AudioChunk objects."""

from __future__ import annotations

import argparse
import math
import queue
import sys
from array import array

try:
    import sounddevice as sd
except ImportError:
    sys.exit("sounddevice is missing. Run: pip install sounddevice")

from academia_audio import AudioChunk, AudioError, AudioFormat, assert_stream_order
from academia_audio.chunker import frames_per_chunk
from academia_audio.schemas import crc32


def rms_level(data: bytes) -> float:
    """Loudness 0.0-1.0 of 16-bit PCM bytes."""
    samples = array("h")
    samples.frombytes(data)
    if sys.byteorder == "big":
        samples.byteswap()
    return math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768


def main() -> int:
    p = argparse.ArgumentParser(description="Stream the real microphone as AudioChunks.")
    p.add_argument("--seconds", type=float, default=10.0, help="how long to record (10)")
    p.add_argument("--chunk-ms", type=int, default=20, help="chunk size in ms (20)")
    p.add_argument("--sample-rate", type=int, default=16000, help="Hz (16000)")
    p.add_argument("--channels", type=int, default=1, help="1 or 2 (1)")
    p.add_argument("--device", type=int, default=None, help="input device id")
    p.add_argument("--list-devices", action="store_true", help="show devices and exit")
    args = p.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return 0

    try:
        fmt = AudioFormat(sample_rate=args.sample_rate, channels=args.channels)
        step = frames_per_chunk(fmt, args.chunk_ms)  # frames per chunk
    except AudioError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    q: "queue.Queue[bytes]" = queue.Queue()
    overflows = 0

    def callback(indata, frames, time_info, status):
        nonlocal overflows
        if status:
            overflows += 1
        q.put(bytes(indata))  # copy: PortAudio reuses its buffer

    print(f"Recording | {fmt} | chunk={args.chunk_ms}ms | {args.seconds}s | Ctrl+C to stop")
    print(f"{'seq':>5} {'timestamp_s':>12} {'size_bytes':>10}  {'level':<22} format")

    chunks: list[AudioChunk] = []
    max_chunks = int(args.seconds * 1000 / args.chunk_ms)
    try:
        with sd.RawInputStream(
            samplerate=fmt.sample_rate,
            channels=fmt.channels,
            dtype="int16",
            blocksize=step,
            device=args.device,
            callback=callback,
        ):
            while len(chunks) < max_chunks:
                data = q.get()
                seq = len(chunks)
                chunk = AudioChunk(
                    sequence_id=seq,
                    timestamp_s=seq * step / fmt.sample_rate,
                    format=fmt,
                    data=data,
                    checksum=crc32(data),
                )
                chunks.append(chunk)
                level = rms_level(data)
                bar = "#" * min(20, int(level * 60))
                print(
                    f"{chunk.sequence_id:>5} {chunk.timestamp_s:>12.3f} "
                    f"{chunk.size_bytes:>10}  {bar:<22} {chunk.format}"
                )
    except KeyboardInterrupt:
        print("\nstopped by user")
    except sd.PortAudioError as err:
        print(f"\nmicrophone error: {err}\nTry --list-devices and pass --device N", file=sys.stderr)
        return 1

    if chunks:
        assert_stream_order(chunks)
        total = sum(c.size_bytes for c in chunks)
        print(f"done | chunks={len(chunks)} bytes={total} input_overflows={overflows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())