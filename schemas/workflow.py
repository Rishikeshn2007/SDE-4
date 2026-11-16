"""Validated workflow proposal schema."""

from dataclasses import dataclass, field


@dataclass
class WorkflowProposal:
    proposal_id: str
    action_type: str
    description: str
    source_ids: list[str] = field(default_factory=list)
    requires_confirmation: bool = True
    status: str = "pending"

    ALLOWED_ACTIONS = {
        "summarize",
        "create_note",
        "draft_message",
        "organize_task",
    }

    ALLOWED_STATUSES = {
        "pending",
        "approved",
        "rejected",
    }

    def validate(self):
        if not isinstance(self.proposal_id, str) or not self.proposal_id.strip():
            raise ValueError("proposal_id must be a non-empty string")

        if not isinstance(self.action_type, str):
            raise ValueError("action_type must be a string")

        if self.action_type not in self.ALLOWED_ACTIONS:
            raise ValueError("Unsupported workflow action")

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be a non-empty string")

        if not isinstance(self.source_ids, list):
            raise ValueError("source_ids must be a list")

        for source_id in self.source_ids:
            if not isinstance(source_id, str) or not source_id.strip():
                raise ValueError("Each source ID must be a non-empty string")

        if not isinstance(self.requires_confirmation, bool):
            raise ValueError("requires_confirmation must be boolean")

        if self.status not in self.ALLOWED_STATUSES:
            raise ValueError("Invalid workflow status")