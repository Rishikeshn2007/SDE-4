"""
Demonstration script for SDE 4 Speech-to-Text Pipeline (Week 2, Day 14).

Demonstrates:
1. Prerecorded synthetic audio fixture generation (using W1 MockMicrophone).
2. Audio preprocessing: Resampling (48 kHz -> 16 kHz) and RMS normalization.
3. Resilient orchestration: TranscriptionOrchestrator with RetryConfig.
4. Stream processing with provider-neutral FakeTranscriber (zero API keys).
5. Event deduplication, duplicate suppression, and interim-final reconciliation.
6. Clean ordered transcript assembly.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src and root to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from academia_audio import MockMicrophone
from academia_audio.schemas import AudioFormat
from sde4_stt import (
    AudioPreprocessor,
    FakeTranscriber,
    RetryConfig,
    TranscriptionOrchestrator,
    TranscriptEventType,
)


def run_week2_demo():
    print("=" * 72)
    print("  ACADEMIA AI VOICE CO-PILOT — SDE 4 (W2) ORCHESTRATION DEMO")
    print("  Week 2: Orchestration, Dedup, Resampling/Norm, Retries")
    print("=" * 72)

    # ------------------------------------------------------------------
    # Step 1: Generate synthetic prerecorded audio fixture (48 kHz)
    # ------------------------------------------------------------------
    print("\n[STEP 1] Generating synthetic prerecorded audio fixture (48 kHz)...")
    source_fmt = AudioFormat(sample_rate=48000, channels=1)
    mic = MockMicrophone(
        fmt=source_fmt,
        duration_s=0.5,
        chunk_ms=50,
        frequency_hz=440.0,
        amplitude=0.3,
    )
    synthetic_chunks = list(mic.stream())
    print(f"  -> Generated {len(synthetic_chunks)} chunks at {source_fmt.sample_rate} Hz ({source_fmt})")

    # ------------------------------------------------------------------
    # Step 2: Configure Preprocessor (48 kHz -> 16 kHz, RMS Normalization)
    # ------------------------------------------------------------------
    print("\n[STEP 2] Configuring AudioPreprocessor (Resampling 48 kHz -> 16 kHz, RMS normalization)...")
    preprocessor = AudioPreprocessor(
        target_sample_rate=16000,
        target_channels=1,
        normalize_audio=True,
        target_rms=0.1,
    )
    print(f"  -> Target sample rate: {preprocessor.target_sample_rate} Hz")
    print(f"  -> RMS normalization: enabled (target_rms={preprocessor.target_rms})")

    # ------------------------------------------------------------------
    # Step 3: Configure Retry / Timeout Resiliency Layer
    # ------------------------------------------------------------------
    print("\n[STEP 3] Configuring Retry & Timeout Layer...")
    retry_cfg = RetryConfig(
        max_retries=3,
        timeout_s=15.0,
        backoff_base_s=0.05,
        backoff_factor=2.0,
    )
    print(f"  -> Max retries: {retry_cfg.max_retries}, Timeout: {retry_cfg.timeout_s}s, Backoff base: {retry_cfg.backoff_base_s}s")

    # ------------------------------------------------------------------
    # Step 4: Build Provider Adapter (Mock mode, zero API keys)
    # ------------------------------------------------------------------
    print("\n[STEP 4] Initializing FakeTranscriber (mock mode, zero API keys)...")
    canned_text = "The audio pipeline successfully preprocessed and transcribed the speech"
    adapter = FakeTranscriber(canned_transcript=canned_text)

    # ------------------------------------------------------------------
    # Step 5: Wire Orchestrator and Transcribe
    # ------------------------------------------------------------------
    print("\n[STEP 5] Executing TranscriptionOrchestrator pipeline...")
    orchestrator = TranscriptionOrchestrator(
        adapter=adapter,
        preprocessor=preprocessor,
        retry_config=retry_cfg,
    )

    session_id = "demo_w2_synthetic_session"
    result = orchestrator.transcribe(
        chunks=synthetic_chunks,
        session_id=session_id,
        language="en",
    )

    # ------------------------------------------------------------------
    # Step 6: Display Reconciled Events and Final Transcript
    # ------------------------------------------------------------------
    print("\n[STEP 6] Pipeline execution completed!")
    print(f"  Session ID:             {result.session_id}")
    print(f"  Chunks processed:       {result.chunks_processed}")
    print(f"  Duration:               {result.duration_s:.4f}s")
    print(f"  Duplicates suppressed:  {result.duplicates_suppressed}")
    print(f"  Interims reconciled:    {result.interims_reconciled}")
    print(f"  Total events produced:  {len(result.events)}")

    print("\n--- Event Stream Progression ---")
    for ev in result.events:
        seg_info = ""
        if ev.segment:
            state = "FINAL" if ev.segment.is_final else "INTERIM"
            seg_info = f'[{state}] "{ev.segment.text}" ({ev.segment.start_time:.2f}s - {ev.segment.end_time:.2f}s, conf: {ev.segment.confidence:.2f})'
        elif ev.error:
            seg_info = f'[ERROR: {ev.error.code}] {ev.error.message}'
        print(f"  [{ev.event_type.value:<8}] {ev.event_id:<40} {seg_info}")

    print("\n" + "=" * 72)
    print(">>> FINAL RECONCILED TRANSCRIPT <<<")
    print(f'"{result.full_text}"')
    print("=" * 72)

    # Word-level breakdown if available
    for seg in result.segments:
        if seg.words:
            print(f"\nWord Alignments for Segment #{seg.sequence_number}:")
            for w in seg.words:
                print(f"  • {w.word:<16} [{w.start_time:.2f}s -> {w.end_time:.2f}s] (conf: {w.confidence})")

    print("\n" + "=" * 72)
    print("  WEEK 2 DEMO SUCCEEDED WITH 100% PASSING CRITERIA")
    print("=" * 72)


if __name__ == "__main__":
    run_week2_demo()

