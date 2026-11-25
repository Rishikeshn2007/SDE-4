"""Demonstrate safe handling when no supporting evidence exists."""

from schemas.context import ReasoningRequest, ScreenContext
from reasoning.grounded_answer import GroundedAnswerGenerator


def main():
    print("WEEK 4 - NO-EVIDENCE FAILURE DEMO")

    context = ScreenContext(
        context_id="week4_empty_context",
        items=[],
        capture_enabled=False,
    )

    request = ReasoningRequest(
        request_id="week4_no_evidence",
        question="Which programming language does the project use?",
        context=context,
    )

    result = GroundedAnswerGenerator().generate(request)

    print("Question:", request.question)
    print("Available evidence: None")
    print("Answer:", result.answer)
    print("Sources:", result.source_ids)

    if result.source_ids:
        raise AssertionError("Unexpected source references")

    print("PASS: No unsupported source was cited.")


if __name__ == "__main__":
    main()
