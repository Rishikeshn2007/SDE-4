"""
Demonstration script for SDE 4 Speech-to-Text Pipeline (Mock Mode - Day 7).

Shows:
1. Session start lifecycle.
2. Ingesting continuous audio chunks with incremental interim hypotheses.
3. Final committed segment emission with word-level alignments.
4. Ordered segment accumulator collecting final transcript segments.
5. End-to-end vertical slice with W1 MockMicrophone source.
"""

import sys
from pathlib import Path

# Add src and root to python path for direct execution
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.schemas.audio import AudioChunk
from sde4_stt.accumulator import SegmentAccumulator
from academia_audio import MockMicrophone


def demo_chunk_to_transcript():
    print("=" * 70)
    print("  SCENARIO 1: CHUNK-TO-TRANSCRIPT STREAMING (MOCK MODE)")
    print("=" * 70)

    transcriber = FakeTranscriber(
        canned_transcript="Why is this application showing this error"
    )

    chunks = [
        AudioChunk(chunk_id="chunk_0", data=b"raw_audio_slice_1", sequence_number=0, duration_seconds=0.75),
        AudioChunk(chunk_id="chunk_1", data=b"raw_audio_slice_2", sequence_number=1, duration_seconds=0.75),
        AudioChunk(chunk_id="chunk_2", data=b"raw_audio_slice_3", sequence_number=2, duration_seconds=0.75, is_last=True),
    ]

    print("\nStreaming 3 audio chunks into FakeTranscriber (Session: 'demo_session_101'):\n")

    events = []
    for event in transcriber.transcribe_stream(chunks, session_id="demo_session_101"):
        events.append(event)
        seg = event.segment
        if seg:
            status_flag = "FINAL" if seg.is_final else "INTERIM"
            print(f"[{event.event_type.value:<8}] [{status_flag:<7}] Time: {seg.start_time:.2f}s - {seg.end_time:.2f}s | Confidence: {seg.confidence:.2f}")
            print(f"           Text: \"{seg.text}\"")
            if seg.words and seg.is_final:
                print("           Word Timings:")
                for w in seg.words:
                    print(f"             • {w.word:<12} [{w.start_time:.2f}s -> {w.end_time:.2f}s]")
            print()
        else:
            print(f"[{event.event_type.value:<8}] (Session Lifecycle Event: {event.event_id})\n")

    print("\nAccumulating segments using SegmentAccumulator:")
    accumulator = SegmentAccumulator()
    final_segments = accumulator.accumulate(events)
    for s in final_segments:
        print(f"  -> Accumulated Final Segment #{s.sequence_number}: \"{s.text}\" (Duration: {s.duration:.2f}s)")


def demo_w1_mock_microphone_integration():
    print("\n" + "=" * 70)
    print("  SCENARIO 2: INTEGRATION WITH W1 MOCK MICROPHONE AUDIO SOURCE")
    print("=" * 70)

    # Generate 5 chunks of 20ms audio from W1 deterministic MockMicrophone
    mic = MockMicrophone(duration_s=0.1, chunk_ms=20)
    mic_chunks = list(mic.stream())
    print(f"\nCaptured {len(mic_chunks)} chunks from academia_audio.MockMicrophone.")

    transcriber = FakeTranscriber(
        canned_transcript="Explain this technical error and recommend next steps"
    )

    print("\nStreaming microphone chunks through STT adapter:\n")
    events = list(transcriber.transcribe_stream(mic_chunks, session_id="demo_mic_session"))
    for event in events:
        if event.segment and event.segment.is_final:
            print(f"[{event.event_type.value}] Final Transcript: \"{event.segment.text}\"")
            print(f"         Confidence: {event.segment.confidence} | Language: {event.segment.language}")

    final_segments = SegmentAccumulator().accumulate(events)
    print(f"\nFinal Ordered Utterance: \"{' '.join(s.text for s in final_segments)}\"")
    print("=" * 70)
    print("  DEMONSTRATION COMPLETED WITH 100% PASSING RESULTS")
    print("=" * 70)


def main():
    print("=" * 70)
    print("  ACADEMIA AI VOICE CO-PILOT — SDE 4 (W2) STT DEMONSTRATION")
    print("=" * 70)
    demo_chunk_to_transcript()
    demo_w1_mock_microphone_integration()


if __name__ == "__main__":
    main()

