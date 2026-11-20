"""
W5 Backend Event-Stream Bridge (Week 3, D19-20).

``EventBridgePublisher`` decouples the STT pipeline from the backend transport
layer by accepting a dependency-injected ``publish_fn`` callable.  This allows
the same publisher to be used with the real W5 ``add_event()`` function in
production or a simple mock in tests.

Usage::

    # In tests – capture published events
    published = []
    publisher = EventBridgePublisher(publish_fn=lambda sid, etype, data: published.append((sid, etype, data)))
    # In production – bridge to W5 backend
    from backend.app.events import add_event
    publisher = EventBridgePublisher(publish_fn=add_event)
"""

from __future__ import annotations

from typing import Callable, List, Optional

from sde4_stt.schemas.transcript import TranscriptEvent


class EventBridgePublisher:
    """Publishes ``TranscriptEvent`` objects to an injectable backend event stream.

    Args:
        publish_fn: A callable with signature
            ``(session_id: str, event_type: str, data: dict) -> None``
            that delivers the event to its destination.  Typically this is the
            W5 backend ``add_event`` function, but can be any sink (a list,
            a logger, a message queue, etc.).

    The publisher serialises each ``TranscriptEvent`` to a plain ``dict`` via
    ``model_dump()``, then calls ``publish_fn(session_id, event_type_value, data)``.

    Errors raised by ``publish_fn`` are caught and recorded in
    ``publish_errors`` so they never propagate into the transcription pipeline.
    """

    def __init__(
        self,
        publish_fn: Callable[[str, str, dict], None],
    ) -> None:
        self._publish_fn = publish_fn
        self._publish_count: int = 0
        self._publish_errors: List[Exception] = []

    @property
    def publish_count(self) -> int:
        """Number of events successfully dispatched to ``publish_fn``."""
        return self._publish_count

    @property
    def publish_errors(self) -> List[Exception]:
        """List of exceptions raised by ``publish_fn`` (never re-raised)."""
        return list(self._publish_errors)

    def publish(self, event: TranscriptEvent) -> None:
        """Serialise and publish a single ``TranscriptEvent``.

        Args:
            event: The transcript event to deliver.
        """
        try:
            data = event.model_dump()
            self._publish_fn(
                event.session_id,
                event.event_type.value,
                data,
            )
            self._publish_count += 1
        except Exception as exc:
            self._publish_errors.append(exc)

    def publish_many(self, events: List[TranscriptEvent]) -> None:
        """Publish a list of events in order."""
        for event in events:
            self.publish(event)

    def reset_stats(self) -> None:
        """Reset publish_count and publish_errors (useful between test runs)."""
        self._publish_count = 0
        self._publish_errors.clear()


def make_no_op_publisher() -> EventBridgePublisher:
    """Return a publisher that discards all events (useful as a safe default)."""
    return EventBridgePublisher(publish_fn=lambda sid, etype, data: None)


__all__ = ["EventBridgePublisher", "make_no_op_publisher"]
