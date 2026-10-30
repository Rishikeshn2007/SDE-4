"""
Synthetic context examples for the W3 Context & Reasoning project.

These examples use manually created data.
No real screen capture is performed.
"""

import sys
from pathlib import Path

# Add the project root to the Python import path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas.context import (
    ContextItem,
    ScreenContext,
    SourceReference,
)


def create_synthetic_context() -> ScreenContext:
    """Create a sample context using synthetic information."""

    source_1 = SourceReference(
        source_id="synthetic_source_001",
        source_type="text",
        description="Synthetic project information",
    )

    source_2 = SourceReference(
        source_id="synthetic_source_002",
        source_type="text",
        description="Synthetic programming information",
    )

    item_1 = ContextItem(
        item_id="synthetic_item_001",
        content="The project uses Java.",
        source=source_1,
    )

    item_2 = ContextItem(
        item_id="synthetic_item_002",
        content="The project includes automated unit tests.",
        source=source_2,
    )

    context = ScreenContext(
        context_id="synthetic_context_001",
        items=[item_1, item_2],
        capture_enabled=False,
    )

    context.validate()

    return context


if __name__ == "__main__":
    sample_context = create_synthetic_context()

    print("Synthetic context created successfully.")
    print(f"Context ID: {sample_context.context_id}")
    print(f"Number of items: {len(sample_context.items)}")
    print(f"Screen capture enabled: {sample_context.capture_enabled}")

    for item in sample_context.items:
        print(f"- {item.content}")