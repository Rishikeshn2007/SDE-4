"""
Event Deduplication, Ordering and Interim/Final Reconciliation (Week 2, D10-11).

Handles:
    * **Duplicate suppression** – events with an already-seen ``event_id``
      are silently dropped.
    * **Interim → final reconciliation** – when a ``FINAL`` event arrives for
      a given ``sequence_number``, any previously buffered ``INTERIM`` for the
      same sequence is discarded.
    * **Ordered output** – ``get_ordered_finals()`` returns all committed
      segments sorted by ``sequence_number``, regardless of arrival order.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

from sde4_stt.schemas.transcript import (
    TranscriptEvent,
    TranscriptEventType,
    TranscriptSegment,
)


class EventDeduplicator:
    """Stateful filter that deduplicates, orders and reconciles transcript events.

    Typical usage::

        dedup = EventDeduplicator()
        for raw_event in adapter_output:
            clean = dedup.process_event(raw_event)
            if clean is not None:
                # forward to downstream
                ...

        # At the end of the stream:
        ordered = dedup.get_ordered_finals()
    """

    def __init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_event(self, event: TranscriptEvent) -> Optional[TranscriptEvent]:
        """Ingest a single event and decide whether to keep or suppress it.

        Rules:
            1. If ``event.event_id`` was already seen → ``None`` (duplicate).
            2. ``START`` / ``COMPLETE`` / ``ERROR`` → store in lifecycle list,
               return the event.
            3. ``INTERIM`` → if a ``FINAL`` already exists for the same
               ``sequence_number``, return ``None`` (superseded).  Otherwise
               buffer as the latest interim and return the event.
            4. ``FINAL`` → store by ``sequence_number`` and discard any
               buffered interim for the same sequence.

        Args:
            event: A ``TranscriptEvent`` to process.

        Returns:
            The event if it should be forwarded downstream, or ``None`` if
            it was suppressed as a duplicate / reconciled interim.
        """
        # Duplicate check
        if event.event_id in self._seen_event_ids:
            self._duplicates_suppressed += 1
            return None
        self._seen_event_ids.add(event.event_id)

        et = event.event_type

        # Lifecycle events
        if et in (
            TranscriptEventType.START,
            TranscriptEventType.COMPLETE,
            TranscriptEventType.ERROR,
        ):
            self._lifecycle_events.append(event)
            return event

        # INTERIM
        if et == TranscriptEventType.INTERIM:
            seg = event.segment
            if seg is None:
                return event  # malformed but let it through
            seq = seg.sequence_number
            # If a FINAL already committed for this sequence → suppress
            if seq in self._final_by_sequence:
                self._interims_reconciled += 1
                return None
            self._interim_by_sequence[seq] = event
            return event

        # FINAL
        if et == TranscriptEventType.FINAL:
            seg = event.segment
            if seg is None:
                return event
            seq = seg.sequence_number
            self._final_by_sequence[seq] = event
            # Discard superseded interim
            if seq in self._interim_by_sequence:
                del self._interim_by_sequence[seq]
                self._interims_reconciled += 1
            return event

        # Unknown type – pass through
        return event

    def process_events(
        self, events: Iterable[TranscriptEvent],
    ) -> List[TranscriptEvent]:
        """Process a batch of events, returning only the non-suppressed ones.

        Args:
            events: Iterable of ``TranscriptEvent`` objects.

        Returns:
            List of events that were *not* suppressed by deduplication or
            reconciliation.
        """
        kept: List[TranscriptEvent] = []
        for ev in events:
            result = self.process_event(ev)
            if result is not None:
                kept.append(result)
        return kept

    def get_ordered_finals(self) -> List[TranscriptSegment]:
        """Return all committed ``FINAL`` segments sorted by ``sequence_number``.

        Returns:
            Ordered list of ``TranscriptSegment`` objects.
        """
        ordered_keys = sorted(self._final_by_sequence.keys())
        segments: List[TranscriptSegment] = []
        for key in ordered_keys:
            seg = self._final_by_sequence[key].segment
            if seg is not None:
                segments.append(seg)
        return segments

    def get_reconciled_stream(self) -> List[TranscriptEvent]:
        """Produce a clean, ordered event stream for downstream consumption.

        The output order is:
            1. ``START`` events
            2. ``FINAL`` events sorted by ``sequence_number``
            3. ``COMPLETE`` events
            4. ``ERROR`` events (appended at the end)

        Returns:
            Re-ordered list of ``TranscriptEvent`` objects.
        """
        starts: List[TranscriptEvent] = []
        completes: List[TranscriptEvent] = []
        errors: List[TranscriptEvent] = []

        for ev in self._lifecycle_events:
            if ev.event_type == TranscriptEventType.START:
                starts.append(ev)
            elif ev.event_type == TranscriptEventType.COMPLETE:
                completes.append(ev)
            elif ev.event_type == TranscriptEventType.ERROR:
                errors.append(ev)

        finals_sorted = [
            self._final_by_sequence[k]
            for k in sorted(self._final_by_sequence.keys())
        ]

        return starts + finals_sorted + completes + errors

    def reset(self) -> None:
        """Clear all internal state so the deduplicator can be reused."""
        self._seen_event_ids: Set[str] = set()
        self._interim_by_sequence: Dict[int, TranscriptEvent] = {}
        self._final_by_sequence: Dict[int, TranscriptEvent] = {}
        self._lifecycle_events: List[TranscriptEvent] = []
        self._duplicates_suppressed: int = 0
        self._interims_reconciled: int = 0

    # ------------------------------------------------------------------
    # Diagnostic properties
    # ------------------------------------------------------------------

    @property
    def num_duplicates_suppressed(self) -> int:
        """Count of events suppressed because their ``event_id`` was seen before."""
        return self._duplicates_suppressed

    @property
    def num_interims_reconciled(self) -> int:
        """Count of ``INTERIM`` events reconciled (discarded) when a ``FINAL``
        arrived for the same ``sequence_number``."""
        return self._interims_reconciled


__all__ = ["EventDeduplicator"]

