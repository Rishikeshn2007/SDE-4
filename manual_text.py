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

    # 6. Save captured audio as WAV for offline diagnostics:
    python manual_text.py --save-wav recording.wav

    # 7. Compare full-recording vs VAD-segmented STT on same audio:
    python manual_text.py --compare
"""

from __future__ import annotations

import argparse
import math
import queue
import struct
import sys
import time
import wave
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


def segment_by_vad(
    chunks: list,
    config,
    merge_gap_s: float = 0.5,
    min_segment_s: float = 1.5,
) -> list:
    """Split captured AudioChunks into speech utterances with merging and filtering.

    Three-stage pipeline:
      1. VAD segmentation — raw SPEECH_START/SPEECH_END boundaries are found
         using ``config``.  A fresh VoiceActivityDetector is created so the
         capture-time VAD state is not reused or corrupted.
      2. Gap merging — adjacent raw segments whose silence gap is ≤ ``merge_gap_s``
         are fused into one.  This prevents normal breath pauses (≈ 0.4 s) from
         creating spurious separate utterances and avoids submitting many tiny
         STT requests.
      3. Minimum-duration filter — merged segments shorter than ``min_segment_s``
         are silently dropped.  Google Web STT's free endpoint returns
         ``UnknownValueError`` on very short audio (empirically < 1.5 s); sending
         sub-threshold segments wastes retry budget and degrades accuracy.

    Args:
        chunks:         Ordered list of AudioChunk objects from the capture loop.
        config:         VADConfig for the segmentation pass.
        merge_gap_s:    Max silence gap (seconds) between two raw segments that
                        should be treated as one utterance.  Default 0.5 s.
        min_segment_s:  Minimum duration (seconds) for a final segment to be
                        returned.  Shorter segments are dropped.  Default 1.5 s.

    Returns:
        List[List[AudioChunk]] — one inner list per kept utterance, in
        chronological order.  Empty list if no qualifying segments found.
    """
    from sde4_stt.vad import VoiceActivityDetector

    if not chunks:
        return []

    vad = VoiceActivityDetector(config)

    # --- Stage 1: raw VAD segmentation (track chunk indices) ---------------
    # Each entry is [start_idx, end_idx] (both inclusive) into ``chunks``.
    raw_segs: list = []
    start_idx: int = -1
    in_speech: bool = False

    for idx, chunk in enumerate(chunks):
        result = vad.process_chunk(chunk)
        if result.transition == "SPEECH_START":
            in_speech = True
            start_idx = idx
        elif in_speech:
            if result.transition == "SPEECH_END":
                raw_segs.append([start_idx, idx])  # inclusive end
                in_speech = False
                start_idx = -1

    # Flush utterance still in progress when recording ended during speech
    if in_speech and start_idx >= 0:
        raw_segs.append([start_idx, len(chunks) - 1])

    if not raw_segs:
        return []

    # --- Stage 2: merge adjacent segments whose gap ≤ merge_gap_s ----------
    merged: list = [raw_segs[0][:]]  # copy
    for seg in raw_segs[1:]:
        prev_end_chunk   = chunks[merged[-1][1]]
        prev_end_time    = prev_end_chunk.timestamp_s + prev_end_chunk.duration_s
        this_start_time  = chunks[seg[0]].timestamp_s
        gap = this_start_time - prev_end_time
        if gap <= merge_gap_s:
            # Extend previous segment to include the gap chunks too
            merged[-1][1] = seg[1]
        else:
            merged.append(seg[:])

    # --- Stage 3: build result lists and apply minimum duration filter ------
    result_segs: list = []
    for start, end in merged:
        seg_chunks = chunks[start : end + 1]
        first = seg_chunks[0]
        last  = seg_chunks[-1]
        dur   = (last.timestamp_s + last.duration_s) - first.timestamp_s
        if dur >= min_segment_s:
            result_segs.append(seg_chunks)

    return result_segs


def analyze_chunks_pcm(chunks: list[AudioChunk]) -> dict:
    """Perform detailed acoustic, amplitude, and clipping analysis on audio chunks.

    Returns diagnostic metrics including:
      - format (sample_rate, channels, bit_depth)
      - timing (total_samples, duration_s)
      - energy (RMS, dBFS)
      - amplitude (peak_abs, peak_pct of full scale)
      - saturation / clipping (exact saturated samples, near-saturated samples,
        maximum consecutive saturated samples / flat-topping run length)
      - health assessment based on genuine clipping detection rather than a
        single near-maximum peak.
    """
    if not chunks:
        return {}
    sample_rate = chunks[0].format.sample_rate
    channels = chunks[0].format.channels
    sample_width = chunks[0].format.sample_width

    all_data = b"".join(c.data for c in chunks)
    n_samples = len(all_data) // sample_width
    if n_samples == 0:
        return {}

    samples = array("h")
    samples.frombytes(all_data)
    if sys.byteorder == "big":
        samples.byteswap()

    sum_sq = 0.0
    peak_abs = 0
    exact_sat = 0
    near_sat = 0
    max_consecutive_sat = 0
    cur_consecutive_sat = 0
    non_zero = 0

    for s in samples:
        abs_s = abs(s)
        if abs_s > peak_abs:
            peak_abs = abs_s
        if s != 0:
            non_zero += 1
        sum_sq += s * s

        # Hard saturation in signed 16-bit PCM: ceiling (+32767) or floor (-32768)
        if s >= 32767 or s <= -32768:
            exact_sat += 1
            cur_consecutive_sat += 1
            if cur_consecutive_sat > max_consecutive_sat:
                max_consecutive_sat = cur_consecutive_sat
        else:
            cur_consecutive_sat = 0

        # Samples within ~2.3% of full scale
        if abs_s >= 32000:
            near_sat += 1

    rms = math.sqrt(sum_sq / n_samples) / 32768.0
    dbfs = 20.0 * math.log10(max(1e-9, rms))
    peak_pct = (peak_abs / 32767.0) * 100.0
    duration_s = n_samples / sample_rate

    # True digital clipping produces flat-topped plateaus of consecutive saturated samples
    if max_consecutive_sat >= 3 or exact_sat > 10:
        assessment = (
            f"GENUINE CLIPPING DETECTED: {exact_sat} saturated samples "
            f"({max_consecutive_sat} max consecutive flat-topped samples)"
        )
        has_clipping = True
    elif peak_abs > 32000:
        assessment = (
            f"HIGH INPUT LEVEL / CLEAN: Peak {peak_abs} ({peak_pct:.1f}% full scale), "
            f"0 flat-topping (near-saturation: {near_sat} samples, {near_sat/n_samples*100.0:.2f}%)"
        )
        has_clipping = False
    elif peak_abs > 1500:
        assessment = f"HEALTHY SPEECH LEVEL: Peak {peak_abs} ({peak_pct:.1f}% full scale), clear dynamic range"
        has_clipping = False
    else:
        assessment = f"LOW INPUT GAIN / NEAR-SILENCE: Peak {peak_abs} ({peak_pct:.1f}% full scale)"
        has_clipping = False

    return {
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width": sample_width,
        "bit_depth": sample_width * 8,
        "total_samples": n_samples,
        "duration_s": duration_s,
        "rms": rms,
        "dbfs": dbfs,
        "peak_abs": peak_abs,
        "peak_pct": peak_pct,
        "non_zero_pct": (non_zero / n_samples) * 100.0 if n_samples > 0 else 0.0,
        "exact_saturation_count": exact_sat,
        "near_saturation_count": near_sat,
        "max_consecutive_sat": max_consecutive_sat,
        "has_clipping": has_clipping,
        "assessment": assessment,
    }


def save_chunks_to_wav(chunks: list[AudioChunk], filepath: str | Path) -> None:
    """Save audio chunks to a standard 16-bit PCM WAV file for offline analysis."""
    if not chunks:
        print("[WARN] No chunks available to save to WAV.")
        return
    fmt = chunks[0].format
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(fmt.channels)
        wf.setsampwidth(fmt.sample_width)
        wf.setframerate(fmt.sample_rate)
        for c in chunks:
            wf.writeframes(c.data)
    total_bytes = sum(len(c.data) for c in chunks)
    dur = total_bytes / (fmt.sample_rate * fmt.channels * fmt.sample_width)
    print(f"\n[WAV SAVED] -> {filepath} ({dur:.2f}s, {fmt.sample_rate}Hz, {fmt.channels}ch, 16-bit PCM)")


def load_chunks_from_wav(filepath: str | Path, chunk_ms: int = 200) -> tuple[list[AudioChunk], int, int, int]:
    """Load audio from a WAV file into AudioChunk slices for repeatable testing."""
    with wave.open(str(filepath), "rb") as wf:
        n_ch = wf.getnchannels()
        sw = wf.getsampwidth()
        fr = wf.getframerate()
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)

    bytes_per_chunk = int(fr * (chunk_ms / 1000.0)) * n_ch * sw
    chunks: list[AudioChunk] = []
    n_chunks = max(1, len(raw_bytes) // bytes_per_chunk) if bytes_per_chunk > 0 else 0
    for i in range(n_chunks):
        cdata = raw_bytes[i * bytes_per_chunk : (i + 1) * bytes_per_chunk]
        if not cdata:
            break
        chunks.append(
            AudioChunk(
                sequence_id=i,
                timestamp_s=round(i * (chunk_ms / 1000.0), 3),
                format=AudioFormat(sample_rate=fr, channels=n_ch, sample_width=sw),
                data=cdata,
            )
        )
    return chunks, fr, n_ch, sw


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
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Disable per-chunk RMS normalization in the preprocessor (prevents noise pumping during pauses)",
    )
    parser.add_argument(
        "--save-wav",
        type=str,
        default=None,
        help="Save captured raw PCM audio to a 16-bit mono WAV file for offline analysis and replay",
    )
    parser.add_argument(
        "--load-wav",
        type=str,
        default=None,
        help="Load audio chunks from an existing WAV file instead of recording live from microphone",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run controlled comparison: Full Recording vs VAD-Segmented STT on the exact same audio",
    )
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

    # Initialize reusable Voice Activity Detector for live metering
    vad = VoiceActivityDetector(
        VADConfig(
            energy_threshold=0.015,
            min_speech_duration_s=0.08,
            min_silence_duration_s=0.35,
            adaptive_noise=True,
        )
    )

    recorded_chunks: list[AudioChunk] = []
    speech_detected_count = 0

    # -----------------------------------------------------------------------
    # Audio Acquisition: Load from WAV or Record from Microphone
    # -----------------------------------------------------------------------
    if args.load_wav:
        print(f"\n[LOADING AUDIO FROM WAV] -> {args.load_wav}")
        try:
            recorded_chunks, wav_sr, wav_ch, wav_sw = load_chunks_from_wav(args.load_wav, args.chunk_ms)
            sample_rate = wav_sr
            channels = wav_ch
            chunks_processed = len(recorded_chunks)
            print(
                f"Successfully loaded {chunks_processed} chunks "
                f"({chunks_processed * args.chunk_ms / 1000.0:.2f}s audio) at {sample_rate}Hz, {channels}ch, {wav_sw*8}-bit PCM.\n"
            )
            # Run VAD across loaded chunks to calculate speech activity
            for c in recorded_chunks:
                res = vad.process_chunk(c)
                if res.is_speech:
                    speech_detected_count += 1
        except Exception as err:
            print(f"[ERROR] Failed to load WAV file '{args.load_wav}': {err}", file=sys.stderr)
            return 1
    else:
        max_chunks = int(args.seconds * 1000 / args.chunk_ms)
        chunks_processed = 0
        peak_level = 0.0

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

                    audio_fmt = AudioFormat(sample_rate=sample_rate, channels=channels, sample_width=2)
                    chunk_obj = AudioChunk(
                        sequence_id=chunks_processed,
                        timestamp_s=round(chunks_processed * (args.chunk_ms / 1000.0), 3),
                        format=audio_fmt,
                        data=data,
                    )
                    recorded_chunks.append(chunk_obj)

                    # Process through VoiceActivityDetector for live VU meter
                    vad_result = vad.process_chunk(chunk_obj)
                    level = vad_result.energy
                    if level > peak_level:
                        peak_level = level
                    is_speech = vad_result.is_speech
                    if is_speech:
                        speech_detected_count += 1

                    # Visual VU meter bar with perceptual square-root scaling
                    bar_len = min(25, int(math.sqrt(level) * 45)) if level > 0 else 0
                    meter = "#" * bar_len + " " * (25 - bar_len)
                    status = "SPEAKING" if is_speech else "LISTENING"

                    elapsed = (chunks_processed + 1) * args.chunk_ms / 1000.0
                    sys.stdout.write(
                        f"\r[{status:<9}] | VU: [{meter}] | Level: {level:0.4f} (Peak: {peak_level:0.4f}) | {elapsed:0.1f}s / {args.seconds}s"
                    )
                    sys.stdout.flush()

                    chunks_processed += 1

        except KeyboardInterrupt:
            print("\n\n[USER STOPPED] Recording stopped early by Ctrl+C.")
        except Exception as err:
            print(f"\n[ERROR] Microphone error: {err}", file=sys.stderr)
            return 1

        # End the carriage-return line cleanly
        print()

    # -----------------------------------------------------------------------
    # Save captured audio to WAV if requested
    # -----------------------------------------------------------------------
    if args.save_wav and recorded_chunks:
        save_chunks_to_wav(recorded_chunks, args.save_wav)

    # -----------------------------------------------------------------------
    # Comprehensive Audio Capture & Signal Diagnostics
    # -----------------------------------------------------------------------
    diag = analyze_chunks_pcm(recorded_chunks)
    if not diag:
        print("[ERROR] No audio data captured or loaded.", file=sys.stderr)
        return 1

    chunks_processed = len(recorded_chunks)
    speech_pct = (speech_detected_count / chunks_processed * 100.0) if chunks_processed > 0 else 0.0

    print("\n" + "=" * 70)
    print("  AUDIO CAPTURE & SIGNAL INTEGRITY DIAGNOSTICS")
    print("=" * 70)
    print(f"• Sample Rate:          {diag['sample_rate']} Hz")
    print(f"• Channel Count:        {diag['channels']} (Mono)")
    print(f"• PCM Bit Depth:        {diag['bit_depth']}-bit signed integer (little-endian)")
    print(f"• Audio Duration:       {diag['duration_s']:.2f}s ({chunks_processed} chunks @ {args.chunk_ms}ms)")
    print(f"• Overall RMS Energy:   {diag['rms']:.5f} ({diag['dbfs']:.1f} dBFS)")
    print(f"• Peak Sample Value:    {diag['peak_abs']} / 32767 ({diag['peak_pct']:.1f}% of full scale)")
    print(f"• Non-Zero Samples:     {diag['non_zero_pct']:.1f}%")
    print(f"• Speech Activity:      {speech_detected_count} / {chunks_processed} chunks ({speech_pct:.1f}% active speech)")
    print(f"• Exact Saturation:     {diag['exact_saturation_count']} samples hitting ±32767/32768")
    print(f"• Near-Saturation:      {diag['near_saturation_count']} samples (abs >= 32000, 97.7%+ full scale)")
    print(f"• Max Saturated Run:    {diag['max_consecutive_sat']} consecutive samples (flat-topping)")
    print(f"• Signal Assessment:    {diag['assessment']}")
    print("=" * 70)

    # Build the orchestrator configuration
    should_normalize = not args.no_normalize
    preprocessor = AudioPreprocessor(target_sample_rate=16000, normalize_audio=should_normalize)
    retry_cfg = RetryConfig(max_retries=2, timeout_s=30.0)

    def _make_orchestrator(sid: str) -> tuple[TranscriptionOrchestrator, any]:
        if args.engine == "real":
            ad = RealSpeechTranscriber(language=args.language, sample_rate=sample_rate)
        else:
            ad = FakeTranscriber(
                canned_transcript="Why is this application showing an error in terminal",
                bytes_per_second=sample_rate * 2,
            )
        orch = TranscriptionOrchestrator(
            adapter=ad,
            preprocessor=preprocessor,
            retry_config=retry_cfg,
        )
        return orch, ad

    # -----------------------------------------------------------------------
    # CONTROLLED EXPERIMENT: Compare Full-Recording vs VAD-Segmented STT
    # -----------------------------------------------------------------------
    if args.compare:
        print("\n" + "=" * 70)
        print("  CONTROLLED EXPERIMENT: FULL RECORDING vs VAD-SEGMENTED STT")
        print("  (Testing the EXACT SAME audio buffer with both strategies)")
        print("=" * 70)

        # ARM 1: Full Recording (Single Request)
        print("\n--- [ARM 1: FULL RECORDING (Single Request)] ---")
        full_orch, _ = _make_orchestrator(f"{session_id}_full")
        t0 = time.monotonic()
        full_res = full_orch.transcribe(
            recorded_chunks,
            session_id=f"{session_id}_full",
            language=args.language,
            sample_rate=sample_rate,
        )
        full_latency = time.monotonic() - t0
        full_err = next((e.error.message for e in full_res.events if e.event_type == TranscriptEventType.ERROR and e.error), None)

        print(f"• Duration Submitted:   {diag['duration_s']:.2f}s ({chunks_processed} chunks)")
        print(f"• Request Latency:      {full_latency:.2f}s")
        print(f"• Status:               {'SUCCESS' if full_res.full_text else ('FAILED: ' + str(full_err))}")
        if full_res.full_text:
            print(f"• Transcribed Text:     \"{full_res.full_text}\"")

        # ARM 2: VAD-Segmented Pipeline
        print("\n--- [ARM 2: VAD-SEGMENTED PIPELINE] ---")
        from sde4_stt.vad import VADConfig as _VADConfig
        seg_cfg = _VADConfig(
            energy_threshold=0.015,
            min_speech_duration_s=0.08,
            min_silence_duration_s=0.60,
            adaptive_noise=True,
        )
        speech_segs = segment_by_vad(recorded_chunks, seg_cfg, merge_gap_s=0.5, min_segment_s=1.5)
        print(f"• VAD Segments Retained: {len(speech_segs)}")

        seg_results_data: list[dict] = []
        for i, seg in enumerate(speech_segs):
            s_diag = analyze_chunks_pcm(seg)
            t_start = seg[0].timestamp_s
            t_end = seg[-1].timestamp_s + seg[-1].duration_s
            dur = t_end - t_start

            seg_orch, _ = _make_orchestrator(f"{session_id}_seg{i}")
            t_start_req = time.monotonic()
            seg_res = seg_orch.transcribe(
                seg,
                session_id=f"{session_id}_seg{i}",
                language=args.language,
                sample_rate=sample_rate,
            )
            seg_latency = time.monotonic() - t_start_req
            seg_err = next((e.error.message for e in seg_res.events if e.event_type == TranscriptEventType.ERROR and e.error), None)

            seg_results_data.append({
                "index": i + 1,
                "start": t_start,
                "end": t_end,
                "duration": dur,
                "chunks": len(seg),
                "rms": s_diag["rms"],
                "peak": s_diag["peak_abs"],
                "peak_pct": s_diag["peak_pct"],
                "clipping": s_diag["has_clipping"],
                "latency": seg_latency,
                "text": seg_res.full_text,
                "error": seg_err,
            })

            status_str = f"\"{seg_res.full_text}\"" if seg_res.full_text else f"FAILED: {seg_err}"
            print(
                f"  UTT {i+1}: [{t_start:.2f}s–{t_end:.2f}s] ({dur:.2f}s, {len(seg)} chunks) | "
                f"RMS: {s_diag['rms']:.4f} | Peak: {s_diag['peak_abs']} ({s_diag['peak_pct']:.1f}%) | "
                f"Latency: {seg_latency:.2f}s -> {status_str}"
            )

        # Comparison Summary Table
        print("\n" + "=" * 70)
        print("  EXPERIMENT COMPARISON SUMMARY")
        print("=" * 70)
        print(f"{'Strategy':<20} | {'Latency':<8} | {'Audio Dur':<10} | {'Recognition Result':<28}")
        print("-" * 70)
        full_desc = f"\"{full_res.full_text}\"" if full_res.full_text else f"FAILED ({full_err or 'No words'})"
        print(f"{'1. Full Recording':<20} | {full_latency:6.2f}s | {diag['duration_s']:6.2f}s    | {full_desc[:28]}")

        combined_vad_text = " ".join(r["text"] for r in seg_results_data if r["text"])
        total_vad_latency = sum(r["latency"] for r in seg_results_data)
        vad_desc = f"\"{combined_vad_text}\"" if combined_vad_text else "FAILED (All segments rejected)"
        print(f"{'2. VAD Segmented':<20} | {total_vad_latency:6.2f}s | {sum(r['duration'] for r in seg_results_data):6.2f}s    | {vad_desc[:28]}")
        print("=" * 70)

        if combined_vad_text:
            print(f"\n>>> VAD ACCUMULATED TRANSCRIPT: <<<")
            print(f"\"{combined_vad_text}\"")
        if full_res.full_text:
            print(f"\n>>> FULL RECORDING TRANSCRIPT: <<<")
            print(f"\"{full_res.full_text}\"")
        return 0

    # -----------------------------------------------------------------------
    # Standard Execution: VAD Segmentation or Single Stream
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  EXECUTING ORCHESTRATED STT PIPELINE...")
    print("=" * 70)

    orchestrator, _ = _make_orchestrator(session_id)

    if args.engine == "real" and recorded_chunks:
        from sde4_stt.vad import VADConfig as _VADConfig

        seg_config = _VADConfig(
            energy_threshold=0.015,
            min_speech_duration_s=0.08,
            min_silence_duration_s=0.60,
            adaptive_noise=True,
        )
        speech_segments = segment_by_vad(
            recorded_chunks,
            seg_config,
            merge_gap_s=0.5,
            min_segment_s=1.5,
        )

        if speech_segments:
            print(
                f"  VAD segmentation: {len(speech_segments)} utterance(s) kept "
                f"after merging and min-duration filter"
            )
            print("  Segment boundaries & signal properties:")
            for i, seg in enumerate(speech_segments):
                s_diag = analyze_chunks_pcm(seg)
                t_start = seg[0].timestamp_s
                t_end = seg[-1].timestamp_s + seg[-1].duration_s
                dur = t_end - t_start
                print(
                    f"    UTT {i + 1}: seq [{seg[0].sequence_id}–{seg[-1].sequence_id}] | "
                    f"{t_start:.2f}s – {t_end:.2f}s ({dur:.2f}s, {len(seg)} chunks) | "
                    f"RMS: {s_diag['rms']:.4f} | Peak: {s_diag['peak_abs']} ({s_diag['peak_pct']:.1f}%) | "
                    f"Sat: {s_diag['exact_saturation_count']} | Run: {s_diag['max_consecutive_sat']}"
                )

            combined_texts: list = []
            total_chunks_proc = 0
            total_dups = 0
            total_interims = 0

            for i, seg in enumerate(speech_segments):
                seg_id = f"{session_id}_seg{i}"
                t_start = seg[0].timestamp_s
                t_end = seg[-1].timestamp_s + seg[-1].duration_s
                dur = t_end - t_start
                print(f"\n  [UTT {i + 1}/{len(speech_segments)}] {len(seg)} chunks  "
                      f"{t_start:.2f}s–{t_end:.2f}s  ({dur:.2f}s)")
                t_req = time.monotonic()
                seg_result = orchestrator.transcribe(
                    seg,
                    session_id=seg_id,
                    language=args.language,
                    sample_rate=sample_rate,
                )
                req_latency = time.monotonic() - t_req
                total_chunks_proc += seg_result.chunks_processed
                total_dups += seg_result.duplicates_suppressed
                total_interims += seg_result.interims_reconciled

                for ev in seg_result.events:
                    if ev.event_type == TranscriptEventType.FINAL and ev.segment:
                        print(f"  Latency:    {req_latency:.2f}s")
                        print(f"  Text:       \"{ev.segment.text}\"")
                        if ev.segment.words:
                            print("  Word Timing (ESTIMATED — equal-division, not provider-supplied):")
                            for w in ev.segment.words:
                                print(f"    • {w.word:<15} [{w.start_time:.2f}s -> {w.end_time:.2f}s] (estimated)")
                        combined_texts.append(ev.segment.text)
                    elif ev.event_type == TranscriptEventType.ERROR and ev.error:
                        print(f"  Latency:    {req_latency:.2f}s")
                        print(f"  [NOTICE]    {ev.error.message}")

            if combined_texts:
                full_text = " ".join(combined_texts)
                print("\n" + "=" * 70)
                print(">>> WHAT YOU SPOKE (ACCUMULATED TRANSCRIPT): <<<")
                print(f"\"{full_text}\"")
                print("=" * 70)
            else:
                print("\nNo spoken words recognized (did you speak loud enough, or was the mic muted?).")

            print(
                f"\nFinished: {chunks_processed} chunks recorded "
                f"({chunks_processed * args.chunk_ms / 1000.0:.1f}s audio)."
            )
            print(
                f"Orchestrator Stats: {total_chunks_proc} chunks processed, "
                f"{total_dups} duplicates suppressed, "
                f"{total_interims} interims reconciled."
            )
            return 0

        # Fallback: VAD found no transitions (all audio is silence)
        print("  VAD: no speech segments detected; transcribing full recording as fallback.")

    # --- Single full-recording transcription (mock mode or VAD fallback) ---
    t_req = time.monotonic()
    result = orchestrator.transcribe(
        recorded_chunks,
        session_id=session_id,
        language=args.language,
        sample_rate=sample_rate,
    )
    req_latency = time.monotonic() - t_req

    found_final = len(result.segments) > 0
    for ev in result.events:
        if ev.event_type == TranscriptEventType.INTERIM and ev.segment:
            print(f"[INTERIM] -> \"{ev.segment.text}\"")
        elif ev.event_type == TranscriptEventType.FINAL and ev.segment:
            print(f"\n[SPEECH TRANSCRIBED]")
            print(f"Text:       \"{ev.segment.text}\"")
            print(f"Duration:   {ev.segment.duration:.2f} seconds")
            print(f"Latency:    {req_latency:.2f} seconds")
            print(f"Confidence: {ev.segment.confidence:.2f}")
            if ev.segment.words:
                print("\nWord Timing Alignments (ESTIMATED - uniform duration distribution):")
                print("  [Note: Google Web Speech returns plain text; word timings are estimated by equal division]")
                for w in ev.segment.words:
                    print(f"  • {w.word:<15} [{w.start_time:.2f}s -> {w.end_time:.2f}s] (estimated)")
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
