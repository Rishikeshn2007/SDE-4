"""Week 3 end-to-end integration demo using synthetic data only."""

from datetime import datetime, timezone

from schemas.context import (
    ContextItem,
    ScreenContext,
    ReasoningRequest,
    SourceReference,
)

from adapters.capture import CaptureAdapter, SyntheticFrame
from adapters.vision import MockVisionAdapter

from observations.observation_builder import (
    ObservationInput,
    ObservationBuilder,
)
from observations.consent_manager import ConsentManager

from reasoning.grounded_answer import GroundedAnswerGenerator
from workflow.planner import WorkflowPlanner
from workflow.handoff import WorkflowHandoff


def main():
    print("=" * 60)
    print("WEEK 3 - END-TO-END INTEGRATION DEMO")
    print("=" * 60)

    # 1. Initialize capture and vision adapters.
    capture = CaptureAdapter(
        opt_in=False,
        sample_every_n=1,
        max_frame_bytes=1024,
    )

    vision = MockVisionAdapter()
    consent = ConsentManager(capture_adapter=capture)

    print("\n1. Initial capture state:", capture.opt_in)

    # 2. Explicitly enable consent.
    consent.enable_consent()

    print("2. Consent enabled:", consent.consent_enabled)

    # 3. Process synthetic frame.
    frame = SyntheticFrame(
        frame_id="week3_frame_001",
        data=b"The project uses Python and includes automated unit tests.",
    )

    captured_frame = capture.process_frame(frame)

    if captured_frame is None:
        raise RuntimeError("Synthetic frame was not captured")

    print("3. Synthetic frame captured:", captured_frame.frame_id)

    # 4. Extract text using mock vision/OCR.
    extracted_text = vision.extract_text(captured_frame)

    print("4. Extracted text:", extracted_text)

    # 5. Convert extracted text into a source-linked observation.
    now = datetime.now(timezone.utc)

    item = ContextItem(
        item_id="week3_item_001",
        content=extracted_text,
        source=SourceReference(
            source_id="week3_source_001",
            source_type="synthetic_frame",
            description="Text extracted from a synthetic frame",
        ),
    )

    observation_builder = ObservationBuilder(
        max_age_seconds=86400
    )

    observations = observation_builder.build(
        [
            ObservationInput(
                item=item,
                timestamp=now,
            )
        ],
        now=now,
    )

    for observation in observations:
        consent.add_observation(observation)

    pending = consent.get_pending_observations()

    print("5. Timestamped observations:", len(pending))

    # 6. Build context only from consented observations.
    context = ScreenContext(
        context_id="week3_context_001",
        items=[observation.item for observation in pending],
        capture_enabled=False,
    )

    request = ReasoningRequest(
        request_id="week3_request_001",
        question="Which programming language does the project use?",
        context=context,
    )

    # 7. Generate a grounded answer.
    generator = GroundedAnswerGenerator()
    result = generator.generate(request)

    print("\n6. Grounded answer:")
    print(result.answer)
    print("Source references:", result.source_ids)

    # 8. Create a workflow proposal.
    planner = WorkflowPlanner()

    proposal = planner.create_proposal(
        request=request,
        action_type="create_note",
        description="Create a note summarizing the project technology.",
        source_ids=result.source_ids,
    )

    # 9. Submit proposal for explicit approval.
    handoff = WorkflowHandoff()
    submission = handoff.submit(proposal)

    print("\n7. Workflow submission:")
    print(submission)

    print("Pending proposals:", len(handoff.get_pending()))

    # 10. Demonstrate approval separately.
    approval = handoff.approve(proposal.proposal_id)

    print("\n8. Workflow approval:")
    print(approval)

    print("Approved proposals:", len(handoff.get_approved()))
    print("Real action executed:", approval["executed"])

    # 11. Withdraw consent and clear pending observations.
    consent.withdraw_consent()

    print("\n9. Consent withdrawal:")
    print("Consent enabled:", consent.consent_enabled)
    print("Capture enabled:", capture.opt_in)
    print("Remaining observations:", len(
        consent.get_pending_observations()
    ))

    print("\n" + "=" * 60)
    print("WEEK 3 INTEGRATION DEMO COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()