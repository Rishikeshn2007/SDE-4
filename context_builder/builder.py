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
        token_budget=200,
        max_items=10,
        max_age_seconds=86400,
    ):
        if token_budget < 1 or max_items < 1 or max_age_seconds < 1:
            raise ValueError("Limits must be positive")

        self.token_budget = token_budget
        self.max_items = max_items
        self.max_age_seconds = max_age_seconds

    def estimate_tokens(self, text):
        """Approximate tokens using whitespace-separated words."""
        return len(text.split())

    def build(self, context_id, entries, query=""):
        now = datetime.now(timezone.utc)

        if not isinstance(entries, list):
            raise ValueError("Entries must be a list")

        query_words = set(query.lower().split())
        valid_entries = []

        for entry in entries:
            if not isinstance(entry, ContextEntry):
                raise ValueError("Invalid context entry")

            entry.item.validate()

            if entry.timestamp.tzinfo is None:
                raise ValueError("Timestamp must include timezone")

            age = (now - entry.timestamp).total_seconds()

            if age > self.max_age_seconds:
                continue

            words = set(entry.item.content.lower().split())

            score = (
                len(query_words & words) / len(query_words)
                if query_words else 0.0
            )

            valid_entries.append((score, entry.timestamp, entry.item))

        # Prefer relevant information, then recent information.
        valid_entries.sort(
            key=lambda x: (x[0], x[1]),
            reverse=True
        )

        selected = []
        used_tokens = 0

        for score, timestamp, item in valid_entries:
            tokens = self.estimate_tokens(item.content)

            if len(selected) >= self.max_items:
                break

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