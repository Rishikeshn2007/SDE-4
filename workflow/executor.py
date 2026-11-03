from workflow.schemas import (
    WorkflowState,
    WorkflowResult,
    ApprovalRequest,
    ToolSpec,
)
from workflow.state_machine import transition
from workflow.mock_tools import MOCK_TOOLS


TOOL_SPECS = {
    "mock_calculator": ToolSpec("mock_calculator"),
    "mock_note_preview": ToolSpec("mock_note_preview"),
}


def validate_plan(plan):
    if not plan.plan_id.strip():
        raise ValueError("Plan ID cannot be empty")

    if not plan.steps:
        raise ValueError("Workflow must contain at least one step")

    step_ids = set()

    for step in plan.steps:
        if not step.step_id.strip():
            raise ValueError("Step ID cannot be empty")

        if step.step_id in step_ids:
            raise ValueError("Duplicate step ID")

        step_ids.add(step.step_id)

        if step.tool_name not in TOOL_SPECS:
            raise ValueError(
                f"Unknown tool: {step.tool_name}"
            )

        if not isinstance(step.inputs, dict):
            raise ValueError("Step inputs must be a dictionary")


def execute_plan(plan, approvals=None):
    approvals = approvals or {}

    try:
        validate_plan(plan)
    except (ValueError, AttributeError) as error:
        return WorkflowResult(
            plan_id=getattr(plan, "plan_id", ""),
            state=WorkflowState.FAILED,
            error=str(error),
        )

    state = WorkflowState.DRAFT
    results = []

    state = transition(state, WorkflowState.RUNNING)

    for step in plan.steps:
        # Consequential steps require approval first.
        if step.consequential:
            if approvals.get(step.step_id) is not True:
                state = transition(
                    state,
                    WorkflowState.AWAITING_APPROVAL,
                )

                request = ApprovalRequest(
                    plan_id=plan.plan_id,
                    step_id=step.step_id,
                    description=(
                        f"Approval required for "
                        f"{step.tool_name}"
                    ),
                )

                return WorkflowResult(
                    plan_id=plan.plan_id,
                    state=state,
                    step_results=results,
                    approval_request=request,
                )

        # Only registered mock tools can execute.
        try:
            output = MOCK_TOOLS[step.tool_name](step.inputs)

            results.append({
                "step_id": step.step_id,
                "output": output,
            })

        except Exception as error:
            state = transition(
                state,
                WorkflowState.FAILED,
            )

            return WorkflowResult(
                plan_id=plan.plan_id,
                state=state,
                step_results=results,
                error=str(error),
            )

    state = transition(state, WorkflowState.SUCCEEDED)

    return WorkflowResult(
        plan_id=plan.plan_id,
        state=state,
        step_results=results,
    )