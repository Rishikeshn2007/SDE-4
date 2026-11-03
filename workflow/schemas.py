from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkflowState(str, Enum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ToolSpec:
    name: str
    consequential: bool = False


@dataclass
class WorkflowStep:
    step_id: str
    tool_name: str
    inputs: dict[str, Any] = field(default_factory=dict)
    consequential: bool = False


@dataclass
class WorkflowPlan:
    plan_id: str
    steps: list[WorkflowStep]


@dataclass
class ApprovalRequest:
    plan_id: str
    step_id: str
    description: str
    approved: bool = False


@dataclass
class WorkflowResult:
    plan_id: str
    state: WorkflowState
    step_results: list[dict[str, Any]] = field(
        default_factory=list
    )
    approval_request: ApprovalRequest | None = None
    error: str | None = None