"""CLI demo: stream the mock microphone and print chunk metadata.

    python -m academia_audio
    python -m academia_audio --duration 1 --chunk-ms 20 --realtime
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Optional, Sequence

from .mock_source import MockMicrophone
from .schemas import AudioError, AudioFormat, assert_stream_order


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="academia_audio", description="Stream the deterministic mock microphone."
    )
    p.add_argument("--duration", type=float, default=2.0, help="stream length in seconds (2.0)")
    p.add_argument("--chunk-ms", type=int, default=20, help="chunk size in ms (20)")
    p.add_argument("--sample-rate", type=int, default=16000, help="Hz (16000)")
    p.add_argument("--channels", type=int, default=1, help="1 or 2 (1)")
    p.add_argument("--limit", type=int, default=None, help="stop after N chunks")
    p.add_argument("--realtime", action="store_true", help="pace output like a live mic")
    p.add_argument("--json", action="store_true", help="print one JSON object per chunk")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        fmt = AudioFormat(sample_rate=args.sample_rate, channels=args.channels)
        mic = MockMicrophone(fmt=fmt, duration_s=args.duration, chunk_ms=args.chunk_ms)
        if not args.json:
            print(f"mock mic | {fmt} | chunk={args.chunk_ms}ms | duration={args.duration}s")
            print(f"{'seq':>5} {'timestamp_s':>12}  {'format':<24}{'size_bytes':>10}")

        digest = hashlib.sha256()
        seen = []
        for chunk in mic.stream(realtime=args.realtime):
            seen.append(chunk)
            digest.update(chunk.data)
            if args.json:
                print(
                    json.dumps(
                        {
                            "sequence_id": chunk.sequence_id,
                            "timestamp_s": chunk.timestamp_s,
                            "format": str(chunk.format),
                            "size_bytes": chunk.size_bytes,
                        }
                    )
                )
            else:
                print(
                    f"{chunk.sequence_id:>5} {chunk.timestamp_s:>12.6f}  "
                    f"{str(chunk.format):<24}{chunk.size_bytes:>10}"
                )
            if args.limit is not None and len(seen) >= args.limit:
                break

        assert_stream_order(seen)
        if not args.json:
            total = sum(c.size_bytes for c in seen)
            print(f"done | chunks={len(seen)} bytes={total} sha256={digest.hexdigest()[:16]}")
        return 0
    except AudioError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
