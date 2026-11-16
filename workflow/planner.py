"""Create workflow proposals from explicit user requests."""

from schemas.context import ReasoningRequest
from schemas.workflow import WorkflowProposal


class WorkflowPlanner:

    def create_proposal(
        self,
        request,
        action_type,
        description,
        source_ids=None,
    ):
        if not isinstance(request, ReasoningRequest):
            raise ValueError("Invalid reasoning request")

        request.validate()

        if action_type not in WorkflowProposal.ALLOWED_ACTIONS:
            raise ValueError("Unsupported workflow action")

        if not isinstance(description, str) or not description.strip():
            raise ValueError("Description must not be empty")

        available_sources = {
            item.source.source_id
            for item in request.context.items
        }

        if source_ids is None:
            source_ids = []

        if not isinstance(source_ids, list):
            raise ValueError("source_ids must be a list")

        for source_id in source_ids:
            if source_id not in available_sources:
                raise ValueError("Source ID is not present in the context")

        proposal = WorkflowProposal(
            proposal_id="proposal_" + request.request_id,
            action_type=action_type,
            description=description.strip(),
            source_ids=list(source_ids),
            requires_confirmation=True,
            status="pending",
        )

        proposal.validate()
        return proposal