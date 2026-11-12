from workflow.schemas import WorkflowPlan, WorkflowStep
from workflow.executor import execute_plan


def show_result(title, result):
    print(f"\n{title}")
    print("State:", result.state.value)
    print("Results:", result.step_results)

    if result.approval_request:
        print("Approval needed for:", result.approval_request.step_id)

    if result.error:
        print("Error:", result.error)

    print("Audit events:", [
        event["event"] for event in result.audit_events
    ])


plan = WorkflowPlan(
    plan_id="demo-001",
    steps=[
        WorkflowStep(
            step_id="step-1",
            tool_name="mock_calculator",
            inputs={"a": 10, "b": 20},
        ),
        WorkflowStep(
            step_id="step-2",
            tool_name="mock_note_preview",
            inputs={
                "title": "Project",
                "content": "Workflow demo",
            },
        ),
        WorkflowStep(
            step_id="step-3",
            tool_name="mock_note_preview",
            inputs={
                "title": "Consequence",
                "content": "Approved simulation",
            },
            consequential=True,
        ),
    ],
)

# Demonstration 1: Approval is missing.
result = execute_plan(plan)
show_result("DEMO 1 - MISSING APPROVAL", result)

# Demonstration 2: Explicit approval is provided.
result = execute_plan(
    plan,
    approvals={"step-3": True},
)
show_result("DEMO 2 - APPROVED EXECUTION", result)

# Demonstration 3: Approval is rejected.
rejected_plan = WorkflowPlan(
    plan_id="demo-rejected",
    steps=[
        WorkflowStep(
            step_id="step-1",
            tool_name="mock_note_preview",
            inputs={
                "title": "Rejected",
                "content": "This tool must not execute",
            },
            consequential=True,
        ),
    ],
)

result = execute_plan(
    rejected_plan,
    approvals={"step-1": False},
)
show_result("DEMO 3 - REJECTED EXECUTION", result)
