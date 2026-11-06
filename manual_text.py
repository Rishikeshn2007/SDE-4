"""
Manual Test: Real Microphone to Speech-to-Text Pipeline (W2).

Captures live audio from your laptop microphone in real-time,
packages it into audio chunks, streams it through the STT adapter
(Real Speech Recognition or Mock), and accumulates the final transcript segments.

Requirements:
    pip install sounddevice pydantic SpeechRecognition

Usage:
    # 1. Real Speech-to-Text (Transcribes what you ACTUALLY speak into the mic):
    python manual_text.py

    # 2. Record for 10 seconds:
    python manual_text.py --seconds 10

    # 3. List audio devices:
    python manual_text.py --list-devices

    # 4. Use specific microphone device index:
    python manual_text.py --device 1

    # 5. Run in mock mode (deterministic fake transcriber):
    python manual_text.py --engine mock
"""

from __future__ import annotations

import argparse
import math
import queue
import sys
import time
from array import array
from pathlib import Path

# Add src and root to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

try:
    import sounddevice as sd
except ImportError:
    sys.exit("sounddevice is missing. Install with: pip install sounddevice")

from sde4_stt.accumulator import SegmentAccumulator
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber
from academia_audio.schemas import AudioChunk, AudioFormat
from sde4_stt.schemas.transcript import TranscriptEventType
from sde4_stt.vad import VoiceActivityDetector, VADConfig
from sde4_stt.orchestrator import TranscriptionOrchestrator
from sde4_stt.preprocessing import AudioPreprocessor
from sde4_stt.retry import RetryConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Live microphone STT pipeline test.")
    parser.add_argument(
        "--engine",
        type=str,
        choices=["real", "mock"],
        default="real",
        help="Transcriber engine: 'real' (actual spoken words) or 'mock' (canned text). Default: 'real'",
    )
    parser.add_argument(
        "--seconds",
        "--duration",
        dest="seconds",
        type=float,
        default=10.0,
        help="Recording time in seconds (default: 10.0)",
    )
    parser.add_argument("--chunk-ms", type=int, default=200, help="Chunk length in milliseconds (default: 200)")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Sample rate in Hz (default: 16000)")
    parser.add_argument("--device", type=int, default=None, help="Input device ID (optional)")
    parser.add_argument("--list-devices", action="store_true", help="List audio input devices and exit")
    parser.add_argument("--language", type=str, default="en-US", help="Language code (default: en-US)")
    args = parser.parse_args()

    if args.list_devices:
        print("\nAvailable Audio Input Devices:")
        print("-" * 50)
        print(sd.query_devices())
        return 0

    sample_rate = args.sample_rate
    channels = 1
    blocksize = int(sample_rate * (args.chunk_ms / 1000.0))

    audio_queue: queue.Queue[bytes] = queue.Queue()
    overflows = 0

    def audio_callback(indata, frames, time_info, status):
        nonlocal overflows
        if status:
            overflows += 1
        audio_queue.put(bytes(indata))

    print("=" * 70)
    print("  ACADEMIA AI VOICE CO-PILOT — REAL MICROPHONE STT TEST")
    print("=" * 70)
    engine_name = "REAL SPEECH RECOGNITION (Google Web STT, free)" if args.engine == "real" else "MOCK DETERMINISTIC TRANSCRIBER"
    print(f"Engine:    {engine_name}")
    print(f"Sampling:  {sample_rate}Hz | 1ch PCM 16-bit | Chunk: {args.chunk_ms}ms")
    print(f"Duration:  {args.seconds}s (or press Ctrl+C to stop earlier)")
    print("=" * 70)
    print(">>> SPEAK INTO YOUR MICROPHONE NOW! <<<\n")

    # Initialize STT Components and VAD
    session_id = f"live_mic_{int(time.time())}"
    if args.engine == "real":
        transcriber = RealSpeechTranscriber(
            language=args.language,
            sample_rate=sample_rate,
        )
    else:
        transcriber = FakeTranscriber(
            canned_transcript="Why is this application showing an error in terminal",
            bytes_per_second=sample_rate * 2,
        )

    # Initialize reusable Voice Activity Detector
    vad = VoiceActivityDetector(
        VADConfig(
            energy_threshold=0.015,
            min_speech_duration_s=0.08,
            min_silence_duration_s=0.35,
            adaptive_noise=True,
        )
    )

    max_chunks = int(args.seconds * 1000 / args.chunk_ms)
    chunks_processed = 0
    speech_detected_count = 0
    recorded_chunks: list[AudioChunk] = []

    try:
        with sd.RawInputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
            blocksize=blocksize,
            device=args.device,
            callback=audio_callback,
        ):
            while chunks_processed < max_chunks:
                try:
                    data = audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                # Package into authoritative W1 AudioChunk
                audio_fmt = AudioFormat(sample_rate=sample_rate, channels=channels, sample_width=2)
                chunk_obj = AudioChunk(
                    sequence_id=chunks_processed,
                    timestamp_s=round(chunks_processed * (args.chunk_ms / 1000.0), 3),
                    format=audio_fmt,
                    data=data,
                )
                recorded_chunks.append(chunk_obj)

                # Process through reusable VoiceActivityDetector
                vad_result = vad.process_chunk(chunk_obj)
                level = vad_result.energy
                is_speech = vad_result.is_speech
                if is_speech:
                    speech_detected_count += 1

                # Visual VU meter bar
                bar_len = min(25, int(level * 100))
                meter = "#" * bar_len + " " * (25 - bar_len)
                status = "SPEAKING" if is_speech else "LISTENING"

                # Dynamic live VU meter
                elapsed = chunks_processed * args.chunk_ms / 1000.0
                sys.stdout.write(
                    f"\r[{status:<9}] | VU: [{meter}] | Audio Level: {level:0.3f} | {elapsed:0.1f}s / {args.seconds}s"
                )
                sys.stdout.flush()

                chunks_processed += 1

    except KeyboardInterrupt:
        print("\n\n[USER STOPPED] Recording stopped early by Ctrl+C.")
    except Exception as err:
        print(f"\n[ERROR] Microphone error: {err}", file=sys.stderr)
        return 1

    print("\n\n" + "=" * 70)
    print("  EXECUTING ORCHESTRATED STT PIPELINE...")
    print("=" * 70)

    # Execute through Week 2 TranscriptionOrchestrator
    preprocessor = AudioPreprocessor(target_sample_rate=16000, normalize_audio=True)
    retry_cfg = RetryConfig(max_retries=2, timeout_s=30.0)
    orchestrator = TranscriptionOrchestrator(
        adapter=transcriber,
        preprocessor=preprocessor,
        retry_config=retry_cfg,
    )

    result = orchestrator.transcribe(
        recorded_chunks,
        session_id=session_id,
        language=args.language,
        sample_rate=sample_rate,
    )

    found_final = len(result.segments) > 0
    for ev in result.events:
        if ev.event_type == TranscriptEventType.INTERIM and ev.segment:
            print(f"[INTERIM] -> \"{ev.segment.text}\"")
        elif ev.event_type == TranscriptEventType.FINAL and ev.segment:
            print(f"\n[SPEECH TRANSCRIBED]")
            print(f"Text:       \"{ev.segment.text}\"")
            print(f"Duration:   {ev.segment.duration:.2f} seconds")
            print(f"Confidence: {ev.segment.confidence:.2f}")
            if ev.segment.words:
                print("\nWord Timing Alignments:")
                for w in ev.segment.words:
                    print(f"  • {w.word:<15} [{w.start_time:.2f}s -> {w.end_time:.2f}s]")
        elif ev.event_type == TranscriptEventType.ERROR and ev.error:
            print(f"\n[NOTICE] {ev.error.message}")

    if found_final and result.full_text:
        print("\n" + "=" * 70)
        print(f">>> WHAT YOU SPOKE (ACCUMULATED TRANSCRIPT): <<<")
        print(f"\"{result.full_text}\"")
        print("=" * 70)
    else:
        print("\nNo spoken words recognized (did you speak loud enough, or was the mic muted?).")

    print(
        f"\nFinished: {chunks_processed} chunks recorded ({chunks_processed * args.chunk_ms / 1000.0:.1f}s audio)."
    )
    print(
        f"Orchestrator Stats: {result.chunks_processed} chunks processed, "
        f"{result.duplicates_suppressed} duplicates suppressed, "
        f"{result.interims_reconciled} interims reconciled."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
