import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from workflow.schemas import (
    WorkflowState,
    WorkflowResult,
    ApprovalRequest,
)
from workflow.state_machine import transition
from workflow.mock_tools import MOCK_TOOLS
from workflow.registry import validate_tool_call


APPROVAL_TTL_SECONDS = 300
MAX_RETRIES = 3


def audit_event(events, event_type, step_id, message):
    events.append({
        "event": event_type,
        "step_id": step_id,
        "message": message,
        "timestamp": time.time(),
    })


def validate_plan(plan):
    if not isinstance(plan.plan_id, str) or not plan.plan_id.strip():
        raise ValueError("Plan ID cannot be empty")

    if not isinstance(plan.steps, list) or not plan.steps:
        raise ValueError("Workflow must contain at least one step")

    steps_by_id = {}

    for step in plan.steps:
        if not isinstance(step.step_id, str) or not step.step_id.strip():
            raise ValueError("Step ID cannot be empty")

        if step.step_id in steps_by_id:
            raise ValueError(f"Duplicate step ID: {step.step_id}")

        if not isinstance(step.dependencies, list):
            raise ValueError(
                f"Dependencies for {step.step_id} must be a list"
            )

        if not isinstance(step.retries, int) or isinstance(step.retries, bool):
            raise ValueError("Retries must be an integer")

        if step.retries < 0 or step.retries > MAX_RETRIES:
            raise ValueError(
                f"Retries must be between 0 and {MAX_RETRIES}"
            )

        if step.timeout_seconds <= 0:
            raise ValueError("Timeout must be greater than zero")

        spec = validate_tool_call(step)

        if step.retries > 0 and not spec.idempotent:
            raise ValueError(
                f"Retries are not allowed for non-idempotent tool: "
                f"{step.tool_name}"
            )

        steps_by_id[step.step_id] = step

    for step in plan.steps:
        if len(step.dependencies) != len(set(step.dependencies)):
            raise ValueError(
                f"Duplicate dependencies in step: {step.step_id}"
            )

        for dependency in step.dependencies:
            if dependency not in steps_by_id:
                raise ValueError(
                    f"Missing dependency '{dependency}' "
                    f"for step '{step.step_id}'"
                )

            if dependency == step.step_id:
                raise ValueError(
                    f"Step '{step.step_id}' cannot depend on itself"
                )

    ordered_steps = []
    visiting = set()
    visited = set()

    def visit(step_id):
        if step_id in visiting:
            raise ValueError(
                f"Circular dependency detected at step: {step_id}"
            )

        if step_id in visited:
            return

        visiting.add(step_id)

        for dependency in steps_by_id[step_id].dependencies:
            visit(dependency)

        visiting.remove(step_id)
        visited.add(step_id)
        ordered_steps.append(steps_by_id[step_id])

    for step in plan.steps:
        visit(step.step_id)

    return ordered_steps


def execute_plan(plan, approvals=None, cancel_event=None):
    approvals = approvals or {}
    results = []
    audit_events = []

    try:
        ordered_steps = validate_plan(plan)
    except (ValueError, AttributeError, TypeError) as error:
        return WorkflowResult(
            plan_id=getattr(plan, "plan_id", ""),
            state=WorkflowState.FAILED,
            error=str(error),
            audit_events=audit_events,
        )

    state = WorkflowState.DRAFT
    state = transition(state, WorkflowState.RUNNING)
    completed_steps = set()

    for step in ordered_steps:

        # Check cancellation before starting another tool.
        if cancel_event is not None and cancel_event.is_set():
            state = transition(state, WorkflowState.CANCELLED)
            audit_event(
                audit_events,
                "cancelled",
                step.step_id,
                "Execution cancelled before the next tool started",
            )
            return WorkflowResult(
                plan_id=plan.plan_id,
                state=state,
                step_results=results,
                audit_events=audit_events,
            )

        if not set(step.dependencies).issubset(completed_steps):
            state = transition(state, WorkflowState.FAILED)
            return WorkflowResult(
                plan_id=plan.plan_id,
                state=state,
                step_results=results,
                error=f"Dependencies not completed for {step.step_id}",
                audit_events=audit_events,
            )

        # Approval checks happen before consequential tools execute.
        if step.consequential:
            approval = approvals.get(step.step_id)

            if approval is None:
                state = transition(
                    state,
                    WorkflowState.AWAITING_APPROVAL,
                )

                request = ApprovalRequest(
                    plan_id=plan.plan_id,
                    step_id=step.step_id,
                    description=f"Approval required for {step.tool_name}",
                    expires_at=time.time() + APPROVAL_TTL_SECONDS,
                )

                audit_event(
                    audit_events,
                    "approval_requested",
                    step.step_id,
                    "Waiting for explicit approval",
                )

                return WorkflowResult(
                    plan_id=plan.plan_id,
                    state=state,
                    step_results=results,
                    approval_request=request,
                    audit_events=audit_events,
                )

            if isinstance(approval, dict):
                approved = approval.get("approved") is True
                expires_at = approval.get("expires_at")
            else:
                approved = approval is True
                expires_at = None

            if not approved:
                state = transition(state, WorkflowState.FAILED)
                audit_event(
                    audit_events,
                    "approval_rejected",
                    step.step_id,
                    "Approval was rejected; tool was not executed",
                )
                return WorkflowResult(
                    plan_id=plan.plan_id,
                    state=state,
                    step_results=results,
                    error="Approval rejected",
                    audit_events=audit_events,
                )

            if expires_at is not None:
                if not isinstance(expires_at, (int, float)):
                    state = transition(state, WorkflowState.FAILED)
                    audit_event(
                        audit_events,
                        "approval_invalid",
                        step.step_id,
                        "Approval expiry timestamp was invalid",
                    )
                    return WorkflowResult(
                        plan_id=plan.plan_id,
                        state=state,
                        step_results=results,
                        error="Invalid approval expiry timestamp",
                        audit_events=audit_events,
                    )

                if time.time() >= expires_at:
                    state = transition(state, WorkflowState.FAILED)
                    audit_event(
                        audit_events,
                        "approval_expired",
                        step.step_id,
                        "Approval expired; tool was not executed",
                    )
                    return WorkflowResult(
                        plan_id=plan.plan_id,
                        state=state,
                        step_results=results,
                        error="Approval expired",
                        audit_events=audit_events,
                    )

            audit_event(
                audit_events,
                "approval_granted",
                step.step_id,
                "Explicit approval accepted",
            )

        spec = validate_tool_call(step)
        timeout_seconds = min(
            step.timeout_seconds,
            spec.timeout_seconds,
        )

        # Retry only idempotent tools and never exceed the limit.
        attempts = 1 + (step.retries if spec.idempotent else 0)

        for attempt in range(1, attempts + 1):
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(
                MOCK_TOOLS[step.tool_name],
                step.inputs,
            )

            try:
                output = future.result(timeout=timeout_seconds)
                executor.shutdown(wait=True)

                results.append({
                    "step_id": step.step_id,
                    "output": output,
                })

                completed_steps.add(step.step_id)

                audit_event(
                    audit_events,
                    "step_succeeded",
                    step.step_id,
                    f"Tool completed on attempt {attempt}",
                )
                break

            except FutureTimeout:
                future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)

                audit_event(
                    audit_events,
                    "step_timeout",
                    step.step_id,
                    f"Tool exceeded {timeout_seconds} seconds "
                    f"on attempt {attempt}",
                )

                if attempt < attempts:
                    continue

                state = transition(state, WorkflowState.FAILED)
                return WorkflowResult(
                    plan_id=plan.plan_id,
                    state=state,
                    step_results=results,
                    error=f"Timeout executing step {step.step_id}",
                    audit_events=audit_events,
                )

            except Exception as error:
                executor.shutdown(wait=False, cancel_futures=True)

                audit_event(
                    audit_events,
                    "step_error",
                    step.step_id,
                    f"Attempt {attempt} failed: {error}",
                )

                if attempt < attempts:
                    continue

                state = transition(state, WorkflowState.FAILED)
                return WorkflowResult(
                    plan_id=plan.plan_id,
                    state=state,
                    step_results=results,
                    error=str(error),
                    audit_events=audit_events,
                )

    state = transition(state, WorkflowState.SUCCEEDED)

    return WorkflowResult(
        plan_id=plan.plan_id,
        state=state,
        step_results=results,
        audit_events=audit_events,
    )
