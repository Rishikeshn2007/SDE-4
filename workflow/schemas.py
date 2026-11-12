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
    required_arguments: tuple[str, ...] = ()
    allowed_arguments: tuple[str, ...] = ()
    permission_scope: str = "safe"
    idempotent: bool = True
    timeout_seconds: float = 5.0


@dataclass
class WorkflowStep:
    step_id: str
    tool_name: str
    inputs: dict[str, Any] = field(default_factory=dict)
    consequential: bool = False
    dependencies: list[str] = field(default_factory=list)
    permission_scope: str = "safe"
    timeout_seconds: float = 5.0
    retries: int = 0


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
    expires_at: float | None = None


@dataclass
class WorkflowResult:
    plan_id: str
    state: WorkflowState
    step_results: list[dict[str, Any]] = field(default_factory=list)
    approval_request: ApprovalRequest | None = None
    error: str | None = None
    audit_events: list[dict[str, Any]] = field(default_factory=list)
