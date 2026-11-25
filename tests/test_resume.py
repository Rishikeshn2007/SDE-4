
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workflow.schemas import (
    WorkflowPlan,
    WorkflowStep,
    WorkflowState,
)
from workflow.executor import execute_plan
import workflow.checkpoint as checkpoint
import workflow.audit as audit


class TestWorkflowResume(unittest.TestCase):

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

    def create_plan(self):
        return WorkflowPlan(
            plan_id="resume-test",
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

    def test_checkpoint_saved_after_success(self):
        plan = self.create_plan()

        result = execute_plan(plan)

        self.assertEqual(result.state, WorkflowState.SUCCEEDED)

        saved = checkpoint.load_checkpoint("resume-test")

        self.assertEqual(
            saved["completed_steps"],
            ["step1", "step2"],
        )
        self.assertEqual(saved["next_step_index"], 2)
        self.assertTrue(saved["plan_signature"])

    def test_resume_does_not_repeat_completed_steps(self):
        plan = self.create_plan()

        first_result = execute_plan(plan)

        self.assertEqual(first_result.state, WorkflowState.SUCCEEDED)

        with patch(
            "workflow.executor.MOCK_TOOLS"
        ) as mock_tools:
            mock_tools.__getitem__.side_effect = AssertionError(
                "Completed steps must not execute again"
            )

            resumed_result = execute_plan(plan, resume=True)

        self.assertEqual(
            resumed_result.state,
            WorkflowState.SUCCEEDED,
        )
        self.assertEqual(len(resumed_result.step_results), 2)

    def test_resume_rejects_modified_plan(self):
        plan = self.create_plan()

        execute_plan(plan)

        modified_plan = self.create_plan()
        modified_plan.steps[0].inputs = {"a": 10, "b": 20}

        result = execute_plan(modified_plan, resume=True)

        self.assertEqual(result.state, WorkflowState.FAILED)
        self.assertIn("Plan has changed", result.error)

    def test_idempotency_keys_are_saved(self):
        plan = self.create_plan()

        execute_plan(plan)

        saved = checkpoint.load_checkpoint("resume-test")

        self.assertIn("step1", saved["idempotency_keys"])
        self.assertIn("step2", saved["idempotency_keys"])
        self.assertNotEqual(
            saved["idempotency_keys"]["step1"],
            saved["idempotency_keys"]["step2"],
        )


if __name__ == "__main__":
    unittest.main()
