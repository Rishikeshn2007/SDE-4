from workflow.schemas import WorkflowPlan, WorkflowStep
from workflow.executor import execute_plan


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

# First run: approval is missing.
result = execute_plan(plan)

print("First run")
print("State:", result.state.value)
print("Results:", result.step_results)

if result.approval_request:
    print(
        "Approval needed for:",
        result.approval_request.step_id,
    )

# Second run: explicit approval for the mock step.
result = execute_plan(
    plan,
    approvals={"step-3": True},
)

print("\nApproved demonstration run")
print("State:", result.state.value)
print("Results:", result.step_results)