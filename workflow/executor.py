
import hashlib
import json
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
from workflow.checkpoint import save_checkpoint, load_checkpoint
from workflow.audit import save_audit_log


APPROVAL_TTL_SECONDS = 300
MAX_RETRIES = 3


def audit_event(events, event_type, step_id, message):
    event = {
        "event": event_type,
        "step_id": step_id,
        "message": message,
        "timestamp": time.time(),
    }
    events.append(event)
    return event


def emit_progress(callback, event):
    if callback is not None:
        callback(event)


def make_idempotency_key(plan_id, step_id):
    raw_key = f"{plan_id}:{step_id}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def make_approval_id(plan_id, step_id):
    raw_key = f"approval:{plan_id}:{step_id}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def make_plan_signature(steps):
    plan_data = []

    for step in steps:
        plan_data.append({
            "step_id": step.step_id,
            "tool_name": step.tool_name,
            "inputs": step.inputs,
            "dependencies": step.dependencies,
            "consequential": step.consequential,
        })

    encoded = json.dumps(plan_data, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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


def execute_plan(
    plan,
    approvals=None,
    cancel_event=None,
    resume=False,
    pause_event=None,
    progress_callback=None,
):
    if approvals is None:
        approvals = {}

    if not isinstance(approvals, (dict, list)):
        return WorkflowResult(
            plan_id=getattr(plan, "plan_id", ""),
            state=WorkflowState.FAILED,
            error="Approvals must be a dictionary or list",
            audit_events=[],
        )

    results = []
    audit_events = []
    completed_steps = set()
    idempotency_keys = {}
    start_index = 0

    try:
        ordered_steps = validate_plan(plan)
        plan_signature = make_plan_signature(ordered_steps)

        if resume:
            checkpoint = load_checkpoint(plan.plan_id)

            if checkpoint.get("plan_signature") != plan_signature:
                raise ValueError(
                    "Plan has changed since checkpoint was created"
                )

            completed_steps = set(
                checkpoint.get("completed_steps", [])
            )
            results = checkpoint.get("step_results", [])
            audit_events = checkpoint.get("audit_events", [])
            idempotency_keys = checkpoint.get("idempotency_keys", {})
            start_index = checkpoint.get("next_step_index", 0)

            if not isinstance(start_index, int) or not (
                0 <= start_index <= len(ordered_steps)
            ):
                raise ValueError("Invalid checkpoint step index")

            audit_event(
                audit_events,
                "workflow_resumed",
                None,
                "Workflow resumed from saved checkpoint",
            )

    except (
        ValueError,
        AttributeError,
        TypeError,
        FileNotFoundError,
    ) as error:
        return WorkflowResult(
            plan_id=getattr(plan, "plan_id", ""),
            state=WorkflowState.FAILED,
            error=str(error),
            audit_events=audit_events,
        )

    state = WorkflowState.DRAFT
    state = transition(state, WorkflowState.RUNNING)

    def persist_checkpoint(next_index, current_state, failed=None):
        save_checkpoint(
            plan_id=plan.plan_id,
            completed_steps=[
                step.step_id
                for step in ordered_steps
                if step.step_id in completed_steps
            ],
            step_results=results,
            next_step_index=next_index,
            state=current_state.value,
            failed_step=failed,
            idempotency_keys=idempotency_keys,
            audit_events=audit_events,
            plan_signature=plan_signature,
        )

        save_audit_log(plan.plan_id, audit_events)

    for index in range(start_index, len(ordered_steps)):
        step = ordered_steps[index]

        if step.step_id in completed_steps:
            continue

        key = idempotency_keys.setdefault(
            step.step_id,
            make_idempotency_key(plan.plan_id, step.step_id),
        )

        if cancel_event is not None and cancel_event.is_set():
            state = transition(state, WorkflowState.CANCELLED)

            event = audit_event(
                audit_events,
                "cancelled",
                step.step_id,
                "Execution cancelled before the next tool started",
            )
            event["idempotency_key"] = key
            emit_progress(progress_callback, event)
            persist_checkpoint(index, state)

            return WorkflowResult(
                plan_id=plan.plan_id,
                state=state,
                step_results=results,
                audit_events=audit_events,
            )

        if pause_event is not None and pause_event.is_set():
            state = transition(state, WorkflowState.PAUSED)

            event = audit_event(
                audit_events,
                "workflow_paused",
                step.step_id,
                "Workflow paused before the next step",
            )
            event["idempotency_key"] = key
            emit_progress(progress_callback, event)
            persist_checkpoint(index, state)

            return WorkflowResult(
                plan_id=plan.plan_id,
                state=state,
                step_results=results,
                audit_events=audit_events,
            )

        if not set(step.dependencies).issubset(completed_steps):
            state = transition(state, WorkflowState.FAILED)
            error = f"Dependencies not completed for {step.step_id}"

            audit_event(
                audit_events,
                "step_error",
                step.step_id,
                error,
            )
            persist_checkpoint(index, state, step.step_id)

            return WorkflowResult(
                plan_id=plan.plan_id,
                state=state,
                step_results=results,
                error=error,
                audit_events=audit_events,
            )

        # Approval handling
        if step.consequential:
            expected_approval_id = make_approval_id(
                plan.plan_id,
                step.step_id,
            )

            if isinstance(approvals, list):
                matching_approvals = [
                    item
                    for item in approvals
                    if isinstance(item, dict)
                    and item.get("plan_id") == plan.plan_id
                    and item.get("step_id") == step.step_id
                ]

                if len(matching_approvals) > 1:
                    state = transition(state, WorkflowState.FAILED)
                    error = "Duplicate approval records detected"

                    event = audit_event(
                        audit_events,
                        "approval_duplicate",
                        step.step_id,
                        error,
                    )
                    event["approval_id"] = expected_approval_id
                    emit_progress(progress_callback, event)
                    persist_checkpoint(index, state, step.step_id)

                    return WorkflowResult(
                        plan_id=plan.plan_id,
                        state=state,
                        step_results=results,
                        error=error,
                        audit_events=audit_events,
                    )

                approval = (
                    matching_approvals[0]
                    if matching_approvals
                    else None
                )

            else:
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
                    approval_id=expected_approval_id,
                )

                event = audit_event(
                    audit_events,
                    "approval_requested",
                    step.step_id,
                    "Waiting for explicit approval",
                )
                event["idempotency_key"] = key
                event["approval_id"] = expected_approval_id

                emit_progress(progress_callback, event)
                persist_checkpoint(index, state)

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
                supplied_approval_id = approval.get("approval_id")

                if (
                    supplied_approval_id is not None
                    and supplied_approval_id != expected_approval_id
                ):
                    state = transition(state, WorkflowState.FAILED)
                    error = "Invalid approval ID"

                    audit_event(
                        audit_events,
                        "approval_rejected",
                        step.step_id,
                        error,
                    )
                    persist_checkpoint(index, state, step.step_id)

                    return WorkflowResult(
                        plan_id=plan.plan_id,
                        state=state,
                        step_results=results,
                        error=error,
                        audit_events=audit_events,
                    )

            else:
                approved = approval is True
                expires_at = None

            if not approved:
                state = transition(state, WorkflowState.FAILED)
                error = "Approval rejected"

                audit_event(
                    audit_events,
                    "approval_rejected",
                    step.step_id,
                    "Approval rejected; tool was not executed",
                )
                persist_checkpoint(index, state, step.step_id)

                return WorkflowResult(
                    plan_id=plan.plan_id,
                    state=state,
                    step_results=results,
                    error=error,
                    audit_events=audit_events,
                )

            if expires_at is not None:
                if (
                    not isinstance(expires_at, (int, float))
                    or isinstance(expires_at, bool)
                ):
                    state = transition(state, WorkflowState.FAILED)
                    error = "Invalid approval expiry timestamp"

                    audit_event(
                        audit_events,
                        "approval_invalid",
                        step.step_id,
                        error,
                    )
                    persist_checkpoint(index, state, step.step_id)

                    return WorkflowResult(
                        plan_id=plan.plan_id,
                        state=state,
                        step_results=results,
                        error=error,
                        audit_events=audit_events,
                    )

                if time.time() >= expires_at:
                    state = transition(state, WorkflowState.FAILED)
                    error = "Approval expired"

                    audit_event(
                        audit_events,
                        "approval_expired",
                        step.step_id,
                        "Approval expired; tool was not executed",
                    )
                    persist_checkpoint(index, state, step.step_id)

                    return WorkflowResult(
                        plan_id=plan.plan_id,
                        state=state,
                        step_results=results,
                        error=error,
                        audit_events=audit_events,
                    )

            event = audit_event(
                audit_events,
                "approval_granted",
                step.step_id,
                "Explicit approval accepted",
            )
            event["idempotency_key"] = key
            event["approval_id"] = expected_approval_id

            emit_progress(progress_callback, event)

        # Tool execution
        spec = validate_tool_call(step)

        timeout_seconds = min(
            step.timeout_seconds,
            spec.timeout_seconds,
        )

        attempts = 1 + (
            step.retries if spec.idempotent else 0
        )

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
                    "idempotency_key": key,
                })

                completed_steps.add(step.step_id)

                event = audit_event(
                    audit_events,
                    "step_succeeded",
                    step.step_id,
                    f"Tool completed on attempt {attempt}",
                )
                event["idempotency_key"] = key

                emit_progress(progress_callback, event)
                persist_checkpoint(index + 1, state)
                break

            except FutureTimeout:
                future.cancel()
                executor.shutdown(
                    wait=False,
                    cancel_futures=True,
                )

                event = audit_event(
                    audit_events,
                    "step_timeout",
                    step.step_id,
                    f"Tool exceeded {timeout_seconds} seconds "
                    f"on attempt {attempt}",
                )
                event["idempotency_key"] = key

                emit_progress(progress_callback, event)

                if attempt < attempts:
                    continue

                state = transition(state, WorkflowState.FAILED)
                persist_checkpoint(index, state, step.step_id)

                return WorkflowResult(
                    plan_id=plan.plan_id,
                    state=state,
                    step_results=results,
                    error=f"Timeout executing step {step.step_id}",
                    audit_events=audit_events,
                )

            except Exception as error:
                executor.shutdown(
                    wait=False,
                    cancel_futures=True,
                )

                event = audit_event(
                    audit_events,
                    "step_error",
                    step.step_id,
                    f"Attempt {attempt} failed: {error}",
                )
                event["idempotency_key"] = key

                emit_progress(progress_callback, event)

                if attempt < attempts:
                    continue

                state = transition(state, WorkflowState.FAILED)
                persist_checkpoint(index, state, step.step_id)

                return WorkflowResult(
                    plan_id=plan.plan_id,
                    state=state,
                    step_results=results,
                    error=str(error),
                    audit_events=audit_events,
                )

    state = transition(state, WorkflowState.SUCCEEDED)

    audit_event(
        audit_events,
        "workflow_succeeded",
        None,
        "All workflow steps completed",
    )

    persist_checkpoint(len(ordered_steps), state)

    return WorkflowResult(
        plan_id=plan.plan_id,
        state=state,
        step_results=results,
        audit_events=audit_events,
    )
