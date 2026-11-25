"""Tests for sde4_stt.dedup — ordering, deduplication & reconciliation."""

import pytest

from sde4_stt.schemas.transcript import (
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
    TranscriptError,
)
from sde4_stt.dedup import EventDeduplicator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seg(seq: int, text: str, is_final: bool = False) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=f"seg_{seq}",
        sequence_number=seq,
        text=text,
        start_time=0.0,
        end_time=1.0,
        is_final=is_final,
        confidence=0.95,
        language="en",
    )


def _evt(
    eid: str,
    etype: TranscriptEventType,
    seq: int | None = None,
    text: str = "hello",
    is_final: bool = False,
) -> TranscriptEvent:
    segment = _seg(seq, text, is_final) if seq is not None else None
    error = None
    if etype == TranscriptEventType.ERROR:
        error = TranscriptError(code="TEST", message="test error")
        segment = None
    return TranscriptEvent(
        event_id=eid,
        session_id="s1",
        event_type=etype,
        timestamp=1.0,
        segment=segment,
        error=error,
    )


# ---------------------------------------------------------------------------
# Duplicate suppression
# ---------------------------------------------------------------------------

class TestDuplicateSuppression:

    def test_duplicate_event_id_suppressed(self):
        dedup = EventDeduplicator()
        e1 = _evt("e1", TranscriptEventType.START)
        assert dedup.process_event(e1) is not None
        assert dedup.process_event(e1) is None  # duplicate
        assert dedup.num_duplicates_suppressed == 1

    def test_different_ids_not_suppressed(self):
        dedup = EventDeduplicator()
        e1 = _evt("e1", TranscriptEventType.START)
        e2 = _evt("e2", TranscriptEventType.COMPLETE)
        assert dedup.process_event(e1) is not None
        assert dedup.process_event(e2) is not None
        assert dedup.num_duplicates_suppressed == 0

    def test_batch_dedup(self):
        dedup = EventDeduplicator()
        e1 = _evt("e1", TranscriptEventType.START)
        events = [e1, e1, e1]
        kept = dedup.process_events(events)
        assert len(kept) == 1
        assert dedup.num_duplicates_suppressed == 2


# ---------------------------------------------------------------------------
# Interim / final reconciliation
# ---------------------------------------------------------------------------

class TestReconciliation:

    def test_interim_suppressed_when_final_exists(self):
        dedup = EventDeduplicator()
        final = _evt("f1", TranscriptEventType.FINAL, seq=0, text="hi", is_final=True)
        interim = _evt("i1", TranscriptEventType.INTERIM, seq=0, text="h")
        dedup.process_event(final)
        result = dedup.process_event(interim)
        assert result is None
        assert dedup.num_interims_reconciled == 1

    def test_final_supersedes_existing_interim(self):
        dedup = EventDeduplicator()
        interim = _evt("i1", TranscriptEventType.INTERIM, seq=0, text="h")
        final = _evt("f1", TranscriptEventType.FINAL, seq=0, text="hello", is_final=True)
        dedup.process_event(interim)
        result = dedup.process_event(final)
        assert result is not None  # final is kept
        assert dedup.num_interims_reconciled == 1
        # Interim no longer in buffer
        segments = dedup.get_ordered_finals()
        assert len(segments) == 1
        assert segments[0].text == "hello"

    def test_multiple_sequences_tracked_independently(self):
        dedup = EventDeduplicator()
        i0 = _evt("i0", TranscriptEventType.INTERIM, seq=0, text="a")
        f0 = _evt("f0", TranscriptEventType.FINAL, seq=0, text="ab", is_final=True)
        i1 = _evt("i1", TranscriptEventType.INTERIM, seq=1, text="c")
        dedup.process_events([i0, f0, i1])
        assert dedup.num_interims_reconciled == 1
        # Interim for seq 1 should still be buffered (no final yet)
        assert 1 in dedup._interim_by_sequence


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

class TestOrdering:

    def test_out_of_order_finals_sorted(self):
        dedup = EventDeduplicator()
        f2 = _evt("f2", TranscriptEventType.FINAL, seq=2, text="c", is_final=True)
        f0 = _evt("f0", TranscriptEventType.FINAL, seq=0, text="a", is_final=True)
        f1 = _evt("f1", TranscriptEventType.FINAL, seq=1, text="b", is_final=True)
        dedup.process_events([f2, f0, f1])
        segments = dedup.get_ordered_finals()
        assert [s.text for s in segments] == ["a", "b", "c"]

    def test_reconciled_stream_order(self):
        dedup = EventDeduplicator()
        start = _evt("s", TranscriptEventType.START)
        f1 = _evt("f1", TranscriptEventType.FINAL, seq=1, text="b", is_final=True)
        f0 = _evt("f0", TranscriptEventType.FINAL, seq=0, text="a", is_final=True)
        complete = _evt("c", TranscriptEventType.COMPLETE)
        dedup.process_events([start, f1, f0, complete])
        stream = dedup.get_reconciled_stream()
        types = [e.event_type for e in stream]
        assert types == [
            TranscriptEventType.START,
            TranscriptEventType.FINAL,  # seq 0
            TranscriptEventType.FINAL,  # seq 1
            TranscriptEventType.COMPLETE,
        ]


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:

    def test_reset_clears_state(self):
        dedup = EventDeduplicator()
        dedup.process_event(_evt("e1", TranscriptEventType.START))
        dedup.process_event(_evt("e1", TranscriptEventType.START))  # dup
        assert dedup.num_duplicates_suppressed == 1
        dedup.reset()
        assert dedup.num_duplicates_suppressed == 0
        # Same event_id should be accepted again after reset
        result = dedup.process_event(_evt("e1", TranscriptEventType.START))
        assert result is not None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_error_events_stored_in_lifecycle(self):
        dedup = EventDeduplicator()
        err = _evt("err1", TranscriptEventType.ERROR)
        result = dedup.process_event(err)
        assert result is not None
        stream = dedup.get_reconciled_stream()
        assert any(e.event_type == TranscriptEventType.ERROR for e in stream)

    def test_empty_input(self):
        dedup = EventDeduplicator()
        kept = dedup.process_events([])
        assert kept == []
        assert dedup.get_ordered_finals() == []

