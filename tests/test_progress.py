
import tempfile
import unittest
from pathlib import Path

from workflow.schemas import WorkflowPlan, WorkflowStep, WorkflowState
from workflow.executor import execute_plan
import workflow.checkpoint as checkpoint
import workflow.audit as audit


class TestWorkflowProgress(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

        self.old_checkpoint_dir = checkpoint.CHECKPOINT_DIR
        self.old_audit_dir = audit.AUDIT_DIR

        checkpoint.CHECKPOINT_DIR = Path(self.temp_dir.name) / "checkpoints"
        audit.AUDIT_DIR = Path(self.temp_dir.name) / "audit_logs"

    def tearDown(self):
        checkpoint.CHECKPOINT_DIR = self.old_checkpoint_dir
        audit.AUDIT_DIR = self.old_audit_dir
        self.temp_dir.cleanup()

    def test_progress_events_are_emitted(self):
        plan = WorkflowPlan(
            plan_id="progress-test",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    tool_name="mock_calculator",
                    inputs={"a": 2, "b": 3},
                ),
                WorkflowStep(
                    step_id="step2",
                    tool_name="mock_calculator",
                    inputs={"a": 4, "b": 5},
                    dependencies=["step1"],
                ),
            ],
        )

        received_events = []

        result = execute_plan(
            plan,
            progress_callback=received_events.append,
        )

        self.assertEqual(result.state, WorkflowState.SUCCEEDED)

        # Both successful steps should emit progress events.
        successful_events = [
            event for event in received_events
            if event["event"] == "step_succeeded"
        ]

        self.assertEqual(len(successful_events), 2)

        # Every successful step should have an idempotency key.
        for event in successful_events:
            self.assertIn("idempotency_key", event)
            self.assertTrue(event["idempotency_key"])

    def test_audit_log_contains_success_events(self):
        plan = WorkflowPlan(
            plan_id="audit-progress-test",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    tool_name="mock_calculator",
                    inputs={"a": 10, "b": 20},
                ),
            ],
        )

        result = execute_plan(plan)

        self.assertEqual(result.state, WorkflowState.SUCCEEDED)

        saved_events = audit.load_audit_log("audit-progress-test")

        event_types = [event["event"] for event in saved_events]

        self.assertIn("step_succeeded", event_types)
        self.assertIn("workflow_succeeded", event_types)


if __name__ == "__main__":
    unittest.main()
