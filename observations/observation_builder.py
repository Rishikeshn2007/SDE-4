"""Timestamped, source-linked observation builder."""

from dataclasses import dataclass
from datetime import datetime, timezone

from schemas.context import ContextItem


@dataclass
class ObservationInput:
    """Context item with its original capture timestamp."""

    item: ContextItem
    timestamp: datetime


@dataclass
class Observation:
    """Validated observation linked to its original source."""

    item: ContextItem
    timestamp: datetime

    @property
    def source_id(self):
        return self.item.source.source_id

    @property
    def content(self):
        return self.item.content


class ObservationBuilder:

    def __init__(self, max_age_seconds=86400):
        if (
            not isinstance(max_age_seconds, (int, float))
            or isinstance(max_age_seconds, bool)
            or max_age_seconds < 1
        ):
            raise ValueError("Maximum age must be positive")

        self.max_age_seconds = max_age_seconds

    def build(self, entries, now=None):
        if not isinstance(entries, list):
            raise ValueError("Entries must be a list")

        if now is None:
            now = datetime.now(timezone.utc)

        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("Current time must include timezone")

        observations = []
        seen = set()

        for entry in entries:
            if not isinstance(entry, ObservationInput):
                raise ValueError("Invalid observation input")

            if not isinstance(entry.timestamp, datetime):
                raise ValueError("Timestamp must be a datetime object")

            if entry.timestamp.tzinfo is None:
                raise ValueError("Timestamp must include timezone")

            entry.item.validate()

            age = (now - entry.timestamp).total_seconds()

            if age < 0:
                raise ValueError("Timestamp cannot be in the future")

            # Drop stale observations.
            if age > self.max_age_seconds:
                continue

            # Identify duplicate content from the same source.
            duplicate_key = (
                entry.item.source.source_id,
                " ".join(entry.item.content.casefold().split()),
            )

            if duplicate_key in seen:
                continue

            seen.add(duplicate_key)

            observations.append(
                Observation(
                    item=entry.item,
                    timestamp=entry.timestamp,
                )
            )

        # Return observations in newest-first order.
        observations.sort(
            key=lambda observation: observation.timestamp,
            reverse=True,
        )

        return observations