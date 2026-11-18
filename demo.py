
import threading

from workflow.schemas import WorkflowPlan, WorkflowStep
from workflow.executor import execute_plan
from workflow.audit import load_audit_log
from workflow.checkpoint import load_checkpoint


def show_result(title, result):
    print(f"\n{'=' * 55}")
    print(title)
    print("=" * 55)

    print("Plan ID:", result.plan_id)
    print("State:", result.state.value)
    print("Completed steps:", [
        item["step_id"] for item in result.step_results
    ])

    if result.approval_request:
        print("Approval required:", result.approval_request.step_id)
        print("Approval ID:", result.approval_request.approval_id)

    if result.error:
        print("Error:", result.error)

    print("Audit events:", [
        event["event"] for event in result.audit_events
    ])


def show_progress(event):
    print(
        f"[PROGRESS] {event['event']} - "
        f"Step: {event.get('step_id')}"
    )


plan = WorkflowPlan(
    plan_id="week3-demo",
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
                "title": "Week 3",
                "content": "Checkpoint and resume demonstration",
            },
        ),
        WorkflowStep(
            step_id="step-3",
            tool_name="mock_note_preview",
            inputs={
                "title": "Approval",
                "content": "Approved mock execution",
            },
            consequential=True,
        ),
    ],
)


# DEMO 1: Execute and pause after the first step.
print("\nDEMO 1: CHECKPOINT CREATION")

pause_event = threading.Event()


def pause_after_first_step(event):
    show_progress(event)

    if event["event"] == "step_succeeded":
        pause_event.set()


result = execute_plan(
    plan,
    pause_event=pause_event,
    progress_callback=pause_after_first_step,
)

show_result("PAUSED WORKFLOW", result)

checkpoint = load_checkpoint(plan.plan_id)
print("\nSaved completed steps:", checkpoint["completed_steps"])
print("Saved next step index:", checkpoint["next_step_index"])


# DEMO 2: Resume without repeating the first step.
print("\nDEMO 2: WORKFLOW RESUME")

result = execute_plan(
    plan,
    resume=True,
    progress_callback=show_progress,
)

show_result("RESUMED WORKFLOW", result)


# DEMO 3: Approve the consequential step.
print("\nDEMO 3: APPROVAL HANDLING")

if result.approval_request:
    approval_id = result.approval_request.approval_id

    approved_result = execute_plan(
        plan,
        resume=True,
        approvals={
            "step-3": {
                "approved": True,
                "approval_id": approval_id,
                "expires_at": result.approval_request.expires_at,
            }
        },
        progress_callback=show_progress,
    )

    show_result("APPROVED WORKFLOW", approved_result)


# DEMO 4: Display saved audit log.
print("\nDEMO 4: SAVED AUDIT LOG")

audit_log = load_audit_log(plan.plan_id)

for event in audit_log:
    print(
        event["event"],
        "| Step:",
        event["step_id"],
        "|",
        event["message"],
    )

print("\nWeek 3 demonstration completed.")
