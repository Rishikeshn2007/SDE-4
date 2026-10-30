"""Demo for the W3 Context & Reasoning project."""

import sys
from pathlib import Path

# Add the project root to the Python import path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reasoning import process_request
from schemas.context import ReasoningRequest
from examples.synthetic_frames import create_synthetic_context


def main():
    """Run a demonstration using synthetic context."""

    context = create_synthetic_context()

    request = ReasoningRequest(
        request_id="demo_request_001",
        question="What language does the project use?",
        context=context,
    )

    result = process_request(request)

    print(f"Request: {request.question}")
    print(f"Answer: {result.answer}")
    print(f"Sources: {result.source_ids}")


if __name__ == "__main__":
    main()