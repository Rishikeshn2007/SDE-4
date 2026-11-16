"""Safe, mock-only workflow proposal handoff with approval gate."""

from schemas.workflow import WorkflowProposal


class WorkflowHandoff:

    def __init__(self):
        self._pending_proposals = []
        self._approved_proposals = []
        self._rejected_proposals = []

    def submit(self, proposal):
        if not isinstance(proposal, WorkflowProposal):
            raise ValueError("A valid WorkflowProposal is required")

        proposal.validate()

        if not proposal.requires_confirmation:
            raise ValueError("Workflow requires explicit confirmation")

        if proposal.status != "pending":
            raise ValueError("Only pending proposals can be submitted")

        all_proposals = (
            self._pending_proposals
            + self._approved_proposals
            + self._rejected_proposals
        )

        if any(
            existing.proposal_id == proposal.proposal_id
            for existing in all_proposals
        ):
            raise ValueError("Proposal has already been submitted")

        self._pending_proposals.append(proposal)

        return {
            "accepted": True,
            "proposal_id": proposal.proposal_id,
            "status": "pending",
            "executed": False,
        }

    def get_pending(self):
        return list(self._pending_proposals)

    def approve(self, proposal_id):
        """Record approval without executing a real-world action."""

        proposal = self._find_pending(proposal_id)

        if proposal is None:
            raise ValueError("Pending proposal not found")

        self._pending_proposals.remove(proposal)
        proposal.status = "approved"
        self._approved_proposals.append(proposal)

        return {
            "approved": True,
            "proposal_id": proposal.proposal_id,
            "status": "approved",
            "executed": False,
        }

    def reject(self, proposal_id):
        """Reject a pending proposal without executing it."""

        proposal = self._find_pending(proposal_id)

        if proposal is None:
            raise ValueError("Pending proposal not found")

        self._pending_proposals.remove(proposal)
        proposal.status = "rejected"
        self._rejected_proposals.append(proposal)

        return {
            "rejected": True,
            "proposal_id": proposal.proposal_id,
            "status": "rejected",
            "executed": False,
        }

    def _find_pending(self, proposal_id):
        for proposal in self._pending_proposals:
            if proposal.proposal_id == proposal_id:
                return proposal

        return None

    def get_approved(self):
        return list(self._approved_proposals)

    def get_rejected(self):
        return list(self._rejected_proposals)

    def clear(self):
        self._pending_proposals.clear()
        self._approved_proposals.clear()
        self._rejected_proposals.clear()