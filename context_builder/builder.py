"""Bounded context builder with recency and relevance selection."""

from dataclasses import dataclass
from datetime import datetime, timezone

from schemas.context import ContextItem, ScreenContext


@dataclass
class ContextEntry:
    item: ContextItem
    timestamp: datetime
    relevance: float = 0.0


class ContextBuilder:

    def __init__(
        self,
        token_budget: int = 200,
        max_items: int = 10,
        max_age_seconds: int = 86400,
    ):
        if token_budget < 1 or max_items < 1 or max_age_seconds < 1:
            raise ValueError("Limits must be positive")

        self.token_budget = token_budget
        self.max_items = max_items
        self.max_age_seconds = max_age_seconds

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens using whitespace-separated words."""
        return len(text.split())

    def build(self, context_id: str, entries: list, query: str = ""):
        now = datetime.now(timezone.utc)

        if not isinstance(entries, list):
            raise ValueError("Entries must be a list")

        query_words = set(query.lower().split())
        valid_entries = []

        for entry in entries:
            if not isinstance(entry, ContextEntry):
                raise ValueError("Invalid context entry")

            if not isinstance(entry.timestamp, datetime):
                raise ValueError("Timestamp must be a datetime object")

            if entry.timestamp.tzinfo is None:
                raise ValueError("Timestamp must include timezone")

            age = (now - entry.timestamp).total_seconds()

            if age < 0:
                raise ValueError("Timestamp cannot be in the future")

            if age > self.max_age_seconds:
                continue

            entry.item.validate()

            content_words = set(entry.item.content.lower().split())

            if query_words:
                score = len(query_words & content_words) / len(query_words)
            else:
                score = entry.relevance

            valid_entries.append(
                (score, entry.timestamp, entry.item)
            )

        # Sort by relevance first and recency second.
        valid_entries.sort(
            key=lambda entry: (entry[0], entry[1]),
            reverse=True
        )

        selected = []
        used_tokens = 0

        for score, timestamp, item in valid_entries:
            if len(selected) >= self.max_items:
                break

            tokens = self.estimate_tokens(item.content)

            if used_tokens + tokens <= self.token_budget:
                selected.append(item)
                used_tokens += tokens

        result = ScreenContext(
            context_id=context_id,
            items=selected,
            capture_enabled=False
        )

        result.validate()
        return result