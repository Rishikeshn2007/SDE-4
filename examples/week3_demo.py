"""Week 3 integration demo using synthetic data only."""

from datetime import datetime, timezone

from schemas.context import (
    ContextItem,
    ScreenContext,
    ReasoningRequest,
    SourceReference,
)

from adapters.capture import CaptureAdapter, SyntheticFrame

from observations.observation_builder import (
    ObservationInput,
    ObservationBuilder,
)

from observations.consent_manager import ConsentManager

from reasoning.grounded_answer import GroundedAnswerGenerator

from workflow.planner import WorkflowPlanner
from workflow.handoff import WorkflowHandoff


def main():

    print("=" * 55)
    print("WEEK 3 - CONTEXT AND REASONING INTEGRATION DEMO")
    print("=" * 55)

    # 1. Create capture adapter with consent disabled.
    print("\n1. Initializing synthetic capture...")

    capture = CaptureAdapter(
        opt_in=False,
        sample_every_n=1,
        max_frame_bytes=1024,
    )

    consent_manager = ConsentManager(
        capture_adapter=capture
    )

    print("Capture enabled initially:", capture.opt_in)

    # 2. Enable consent and process a synthetic frame.
    print("\n2. Enabling consent...")

    consent_manager.enable_consent()

    frame = SyntheticFrame(
        frame_id="demo_frame_001",
        data=b"synthetic project information",
    )

    captured_frame = capture.process_frame(frame)

    print("Consent enabled:", consent_manager.consent_enabled)
    print("Synthetic frame captured:", captured_frame is not None)

    # 3. Build timestamped observations.
    print("\n3. Building timestamped observations...")

    now = datetime.now(timezone.utc)

    item = ContextItem(
        item_id="demo_item_001",
        content="The project uses Python and includes automated unit tests.",
        source=SourceReference(
            source_id="demo_source_001",
            source_type="synthetic",
            description="Synthetic project information",
        ),
    )

    observation_input = ObservationInput(
        item=item,
        timestamp=now,
    )

    observation_builder = ObservationBuilder(
        max_age_seconds=86400
    )

    observations = observation_builder.build(
        [observation_input],
        now=now,
    )

    for observation in observations:
        consent_manager.add_observation(observation)

    pending = consent_manager.get_pending_observations()

    print("Observations created:", len(observations))
    print("Pending observations:", len(pending))

    # 4. Build reasoning request from consented observations.
    print("\n4. Preparing reasoning request...")

    context = ScreenContext(
        context_id="demo_context_001",
        items=[observation.item for observation in pending],
        capture_enabled=False,
    )

    request = ReasoningRequest(
        request_id="demo_request_001",
        question="What programming language does the project use?",
        context=context,
    )

    # 5. Generate grounded answer.
    print("\n5. Generating grounded answer...")

    answer_generator = GroundedAnswerGenerator()
    result = answer_generator.generate(request)

    print("Answer:", result.answer)
    print("Source IDs:", result.source_ids)

    # 6. Create a workflow proposal.
    print("\n6. Creating workflow proposal...")

    planner = WorkflowPlanner()

    proposal = planner.create_proposal(
        request=request,
        action_type="create_note",
        description="Create a note about the project technology.",
        source_ids=result.source_ids,
    )

    # 7. Submit proposal for approval.
    print("\n7. Performing mock workflow handoff...")

    handoff = WorkflowHandoff()
    handoff_result = handoff.submit(proposal)

    print("Handoff result:", handoff_result)
    print("Pending proposals:", len(handoff.get_pending()))

    # 8. Demonstrate consent withdrawal.
    print("\n8. Withdrawing consent...")

    consent_manager.withdraw_consent()

    print("Consent enabled:", consent_manager.consent_enabled)
    print("Capture enabled:", capture.opt_in)
    print("Pending observations:", len(
        consent_manager.get_pending_observations()
    ))

    print("\n" + "=" * 55)
    print("WEEK 3 INTEGRATION DEMO COMPLETED")
    print("=" * 55)


if __name__ == "__main__":
    main()