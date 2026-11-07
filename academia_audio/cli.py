"""CLI demo: stream the mock microphone and print chunk metadata.

    python -m academia_audio
    python -m academia_audio --duration 1 --chunk-ms 20 --realtime
    python -m academia_audio --demo     # Week 2 interactive pipeline demo
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Optional, Sequence

from .buffer import BoundedAudioBuffer
from .device import MockDeviceAdapter
from .lifecycle import AudioPipeline, LifecycleState
from .mock_source import MockMicrophone
from .schemas import AudioError, AudioFormat, assert_stream_order
from .vad import MockVAD


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
    p.add_argument("--vad", action="store_true", help="evaluate and display VAD speech detection")
    p.add_argument("--demo", action="store_true", help="run a short demonstration of the Week 2 pipeline")
    return p


def run_week2_demo() -> int:
    """Demonstrate the Week 2 Audio & VAD pipeline: device adapter, lifecycle, VAD, and buffer."""
    print("=" * 70)
    print("  ACADEMIA AI VOICE BOT - WEEK 2 PIPELINE DEMO")
    print("=" * 70)

    # 1. Device Adapter
    adapter = MockDeviceAdapter()
    devs = adapter.list_devices()
    print(f"\n1. Device Selection: Found {len(devs)} devices")
    for d in devs:
        def_tag = " (default)" if d.is_default else ""
        print(f"   - [{d.id}] {d.name} ({d.sample_rate}Hz/{d.channels}ch){def_tag}")
    adapter.select_device("mock-default")
    print(f"   Active device: {adapter.get_selected_device().name}")
    print(f"   Permission state: {adapter.get_permission_state().value}")

    # 2. Lifecycle & Pipeline Setup
    fmt = AudioFormat(16000, 1)
    buffer = BoundedAudioBuffer(capacity=8)
    vad = MockVAD(energy_threshold=0.05, min_speech_duration_ms=60.0)
    pipeline = AudioPipeline(adapter=adapter, buffer=buffer, vad=vad, fmt=fmt)

    print(f"\n2. Lifecycle State Machine:")
    print(f"   Initial state: {pipeline.state.value}")
    pipeline.start()
    print(f"   pipeline.start() -> state: {pipeline.state.value}")

    # 3. Stream through VAD & Buffer
    print(f"\n3. Streaming Chunks (VAD & Buffer):")
    print(f"   {'seq':>5} {'timestamp':>10} {'RMS':>8} {'Speech?':<8} {'Buffer':>8}")
    for _ in range(12):
        item = pipeline.step()
        if item is None:
            break
        chunk, vres = item
        speech_str = "YES" if vres.is_speech else "NO"
        print(
            f"   {chunk.sequence_id:>5} {chunk.timestamp_s:>9.3f}s {vres.energy:>8.4f} "
            f"{speech_str:<8} {pipeline.buffer.size:>4}/{pipeline.buffer.capacity}"
        )

    print(f"\n4. Backpressure & Overflow Accounting:")
    print(f"   Buffer capacity: {pipeline.buffer.capacity} chunks")
    print(f"   Current buffered: {pipeline.buffer.size} chunks")
    print(f"   Dropped on overflow: {pipeline.buffer.dropped_chunks} chunks")

    # 5. Pause & Resume
    print(f"\n5. Pause & Resume Test:")
    pipeline.pause()
    print(f"   pipeline.pause()  -> state: {pipeline.state.value}")
    pipeline.resume()
    print(f"   pipeline.resume() -> state: {pipeline.state.value}")

    # 6. Stop & Buffer Release
    print(f"\n6. Stop & Resource Release:")
    print(f"   Buffer size before stop: {pipeline.buffer.size}")
    pipeline.stop()
    print(f"   pipeline.stop()   -> state: {pipeline.state.value}")
    print(f"   Buffer size after stop:  {pipeline.buffer.size} (Buffer released: {pipeline.buffer.is_empty})")

    print("\n" + "=" * 70)
    print("  DEMO COMPLETE - ALL WEEK 2 REQUIREMENTS OPERATIONAL")
    print("=" * 70)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.demo:
        return run_week2_demo()

    try:
        fmt = AudioFormat(sample_rate=args.sample_rate, channels=args.channels)
        mic = MockMicrophone(fmt=fmt, duration_s=args.duration, chunk_ms=args.chunk_ms)
        vad = MockVAD() if args.vad else None

        if not args.json:
            vad_header = "  vad_speech" if args.vad else ""
            print(f"mock mic | {fmt} | chunk={args.chunk_ms}ms | duration={args.duration}s")
            print(f"{'seq':>5} {'timestamp_s':>12}  {'format':<24}{'size_bytes':>10}{vad_header}")

        digest = hashlib.sha256()
        seen = []
        for chunk in mic.stream(realtime=args.realtime):
            seen.append(chunk)
            digest.update(chunk.data)
            vres = vad.process_chunk(chunk) if vad else None

            if args.json:
                payload = {
                    "sequence_id": chunk.sequence_id,
                    "timestamp_s": chunk.timestamp_s,
                    "format": str(chunk.format),
                    "size_bytes": chunk.size_bytes,
                }
                if vres:
                    payload["is_speech"] = vres.is_speech
                    payload["energy"] = vres.energy
                print(json.dumps(payload))
            else:
                vad_str = f"  {'SPEECH' if vres.is_speech else 'SILENCE'}" if vres else ""
                print(
                    f"{chunk.sequence_id:>5} {chunk.timestamp_s:>12.6f}  "
                    f"{str(chunk.format):<24}{chunk.size_bytes:>10}{vad_str}"
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
