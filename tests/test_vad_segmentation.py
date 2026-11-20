"""
Tests for the VAD-guided utterance segmentation helper in manual_text.py.

Covers the three-stage pipeline:
  1. Raw VAD segmentation  (SPEECH_START / SPEECH_END boundaries)
  2. Gap merging           (adjacent segments within merge_gap_s fused)
  3. Minimum-duration filter (sub-threshold segments dropped)

Also verifies chunk ordering, boundary timestamps, and edge-cases (all
silence, all speech, empty input).
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

# Allow importing manual_text helper from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from academia_audio.schemas import AudioChunk, AudioFormat
from sde4_stt.vad import VADConfig

from manual_text import segment_by_vad

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SR       = 16000          # sample rate Hz
CHUNK_MS = 200            # chunk length ms
N_SAMP   = SR * CHUNK_MS // 1000   # 3200 samples per chunk
FMT      = AudioFormat(sample_rate=SR, channels=1)

# Amplitudes for synthesised audio
AMP_SPEECH  = 8_000   # well above energy_threshold=0.015
AMP_SILENCE = 50      # well below threshold

# Standard segmentation VAD config (matches the updated manual_text.py call)
SEG_CFG = VADConfig(
    energy_threshold=0.015,
    min_speech_duration_s=0.08,
    min_silence_duration_s=0.60,
    adaptive_noise=True,
)


def make_chunk(seq: int, amplitude: int) -> AudioChunk:
    """Build a 200 ms AudioChunk at the given sequence position and amplitude."""
    data = struct.pack(f"<{N_SAMP}h", *([amplitude] * N_SAMP))
    return AudioChunk(
        sequence_id=seq,
        timestamp_s=round(seq * CHUNK_MS / 1000.0, 3),
        format=FMT,
        data=data,
    )


def build_pattern(*runs) -> list:
    """Build a chunk list from (amplitude, count) pairs."""
    chunks = []
    seq = 0
    for amp, count in runs:
        for _ in range(count):
            chunks.append(make_chunk(seq, amp))
            seq += 1
    return chunks


def total_duration(seg: list) -> float:
    """Return the wall-clock duration of a segment list in seconds."""
    return (seg[-1].timestamp_s + seg[-1].duration_s) - seg[0].timestamp_s


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSegmentByVadBasic:
    """Basic segmentation correctness."""

    def test_empty_input_returns_empty(self):
        assert segment_by_vad([], SEG_CFG) == []

    def test_all_silence_returns_empty(self):
        chunks = build_pattern((AMP_SILENCE, 20))
        segs = segment_by_vad(chunks, SEG_CFG)
        assert segs == [], "All-silence recording must yield zero segments."

    def test_all_speech_no_internal_silence_gives_one_segment(self):
        chunks = build_pattern((AMP_SILENCE, 2), (AMP_SPEECH, 30), (AMP_SILENCE, 2))
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=0.0)
        assert len(segs) == 1, (
            f"Continuous speech should yield 1 segment; got {len(segs)}"
        )

    def test_two_distinct_utterances_with_long_gap(self):
        # 2 utterances separated by 1.4 s of silence (7 chunks > merge_gap_s=0.5s)
        chunks = build_pattern(
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 15),    # utterance 1 (3.0 s)
            (AMP_SILENCE, 7),    # 1.4 s gap  > merge_gap_s
            (AMP_SPEECH, 15),    # utterance 2 (3.0 s)
            (AMP_SILENCE, 3),
        )
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=1.5)
        assert len(segs) == 2, (
            f"Two utterances with 1.4s gap should NOT be merged; got {len(segs)}"
        )

    def test_chronological_ordering_no_gaps_no_duplicates(self):
        """Every segment chunk must appear in strictly increasing sequence_id order."""
        chunks = build_pattern(
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 10),
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 10),
            (AMP_SILENCE, 3),
        )
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=0.0)
        all_seqs = [c.sequence_id for seg in segs for c in seg]
        assert all_seqs == sorted(set(all_seqs)), (
            "Chunk sequence IDs in segments must be strictly increasing (no duplicates, no reorder)."
        )

    def test_recording_ends_during_speech_flushes_segment(self):
        """An utterance in progress when the recording ends must be included."""
        chunks = build_pattern((AMP_SILENCE, 3), (AMP_SPEECH, 20))  # ends in speech
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=1.5)
        assert len(segs) == 1
        assert len(segs[0]) > 0


class TestSegmentByVadMerging:
    """Gap-merging stage correctness."""

    def test_breath_pause_does_not_split_utterance(self):
        """A 0.4s (2-chunk) pause must NOT split the utterance when merge_gap_s=0.5."""
        chunks = build_pattern(
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 8),     # first word group
            (AMP_SILENCE, 2),    # 0.4 s breath pause
            (AMP_SPEECH, 8),     # second word group
            (AMP_SILENCE, 4),
        )
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=0.0)
        assert len(segs) == 1, (
            f"0.4s breath pause must be merged into one segment; got {len(segs)}"
        )

    def test_gap_above_merge_threshold_does_split(self):
        """A large silence gap keeps 2 separate segments.

        With min_silence_duration_s=0.60, the SPEECH_END hangover consumes
        ~0.6 s of the inter-segment silence.  The *residual* gap (total silence
        − hangover) is what segment_by_vad computes.  To produce a residual gap
        > merge_gap_s=0.5 we need total_silence > 1.1 s, so we use 7 chunks
        (1.4 s): residual = 1.4 − 0.6 = 0.8 s > 0.5 s.
        """
        chunks = build_pattern(
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 10),
            (AMP_SILENCE, 7),    # 1.4 s total; residual ~0.8 s > merge_gap_s=0.5
            (AMP_SPEECH, 10),
            (AMP_SILENCE, 3),
        )
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=0.0)
        assert len(segs) == 2, (
            f"Large gap (residual ~0.8s) must NOT be merged; got {len(segs)}"
        )

    def test_merged_segment_includes_gap_chunks(self):
        """When two raw segments are merged, their gap chunks are included."""
        chunks = build_pattern(
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 8),
            (AMP_SILENCE, 2),    # 0.4 s gap — will be merged
            (AMP_SPEECH, 8),
            (AMP_SILENCE, 4),
        )
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=0.0)
        assert len(segs) == 1
        # merged segment should span both speech groups + the silence gap
        dur = total_duration(segs[0])
        assert dur >= 2.0, f"Merged segment too short: {dur:.2f}s"

    def test_multiple_merges_work_correctly(self):
        """Three short utterances with breath pauses are fused into one."""
        chunks = build_pattern(
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 5),
            (AMP_SILENCE, 2),   # 0.4 s
            (AMP_SPEECH, 5),
            (AMP_SILENCE, 2),   # 0.4 s
            (AMP_SPEECH, 5),
            (AMP_SILENCE, 4),
        )
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=0.0)
        assert len(segs) == 1


class TestSegmentByVadMinDuration:
    """Minimum-duration filter stage correctness."""

    def test_long_segments_pass_minimum_filter(self):
        chunks = build_pattern(
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 20),   # 4.0 s >> 1.5 s
            (AMP_SILENCE, 5),
        )
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=1.5)
        assert len(segs) == 1
        assert total_duration(segs[0]) >= 1.5

    def test_min_duration_zero_keeps_all_segments(self):
        """With min_segment_s=0.0, more segments are kept than with min_segment_s=1.5."""
        chunks = build_pattern(
            (AMP_SILENCE, 10),
            (AMP_SPEECH, 2),    # tiny ~0.4s segment
            (AMP_SILENCE, 10),
        )
        segs_all      = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=0.0)
        segs_filtered = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=1.5)
        assert len(segs_all) >= len(segs_filtered)

    def test_all_filtered_segments_meet_min_duration(self):
        """Every returned segment must satisfy the minimum duration threshold."""
        chunks = build_pattern(
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 10),
            (AMP_SILENCE, 10),
            (AMP_SPEECH, 2),
            (AMP_SILENCE, 10),
        )
        min_s = 1.5
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=min_s)
        for seg in segs:
            assert total_duration(seg) >= min_s, (
                f"Segment of {total_duration(seg):.2f}s slipped past min_segment_s={min_s}"
            )


class TestSegmentByVadTimestamps:
    """Segment boundary timestamp correctness."""

    def test_segment_end_time_after_start(self):
        chunks = build_pattern(
            (AMP_SILENCE, 5),
            (AMP_SPEECH, 15),
            (AMP_SILENCE, 5),
        )
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=1.5)
        for seg in segs:
            t_start = seg[0].timestamp_s
            t_end   = seg[-1].timestamp_s + seg[-1].duration_s
            assert t_end > t_start

    def test_no_chunks_duplicated_across_segments(self):
        """The same chunk must not appear in two different segments."""
        chunks = build_pattern(
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 10),
            (AMP_SILENCE, 10),
            (AMP_SPEECH, 10),
            (AMP_SILENCE, 3),
        )
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=1.5)
        all_ids = [c.sequence_id for seg in segs for c in seg]
        assert len(all_ids) == len(set(all_ids)), "Duplicate chunk sequence IDs across segments!"

    def test_chunk_timestamps_monotonically_increasing_within_segment(self):
        chunks = build_pattern(
            (AMP_SILENCE, 3),
            (AMP_SPEECH, 20),
            (AMP_SILENCE, 3),
        )
        segs = segment_by_vad(chunks, SEG_CFG, merge_gap_s=0.5, min_segment_s=1.5)
        for seg in segs:
            for a, b in zip(seg, seg[1:]):
                assert b.timestamp_s > a.timestamp_s, (
                    f"Non-monotonic timestamps: {a.timestamp_s} -> {b.timestamp_s}"
                )
