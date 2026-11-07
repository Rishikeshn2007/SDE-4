"""Demo for Week 1 and Week 2 Context & Reasoning project."""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reasoning import process_request
from schemas.context import (
    ReasoningRequest,
    SourceReference,
    ContextItem,
)
from examples.synthetic_frames import create_synthetic_context

from adapters.capture import CaptureAdapter, SyntheticFrame
from adapters.vision import MockVisionAdapter
from context_builder.builder import ContextBuilder, ContextEntry
from llm.client import LLMAdapter


def main():
    print("\n===== WEEK 1 DEMO =====")

    context = create_synthetic_context()

    request = ReasoningRequest(
        request_id="demo_request_001",
        question="What language does the project use?",
        context=context,
    )

    result = process_request(request)

    print("Question:", request.question)
    print("Answer:", result.answer)
    print("Sources:", result.source_ids)

    print("\n===== WEEK 2 DEMO =====")

    # 1. Capture synthetic frame with explicit opt-in
    capture = CaptureAdapter(opt_in=False)
    capture.set_opt_in(True)

    frame = SyntheticFrame(
        frame_id="week2_frame_001",
        data=b"The project uses Python and automated unit tests."
    )

    captured_frame = capture.process_frame(frame)
    print("1. Synthetic frame captured successfully.")

    # 2. Extract text using mock vision adapter
    vision = MockVisionAdapter()
    extracted_text = vision.extract_text(captured_frame)
    print("2. Extracted text:", extracted_text)

    # 3. Build bounded context
    source = SourceReference(
        source_id="week2_source_001",
        source_type="synthetic"
    )

    item = ContextItem(
        item_id="week2_item_001",
        content=extracted_text,
        source=source
    )

    entry = ContextEntry(
        item=item,
        timestamp=datetime.now(timezone.utc)
    )

    builder = ContextBuilder(
        token_budget=50,
        max_items=5
    )

    week2_context = builder.build(
        context_id="week2_context_001",
        entries=[entry],
        query="Python project"
    )

    print("3. Context built successfully.")
    print("Context items:", len(week2_context.items))

    # 4. Generate response using mock LLM
    week2_request = ReasoningRequest(
        request_id="week2_request_001",
        question="What language does the project use?",
        context=week2_context
    )

    llm = LLMAdapter()
    week2_result = llm.generate(week2_request)

    print("4. Mock LLM response:", week2_result.answer)
    print("Sources:", week2_result.source_ids)

    print("\n===== DEMO COMPLETED SUCCESSFULLY =====")


if __name__ == "__main__":
    main()