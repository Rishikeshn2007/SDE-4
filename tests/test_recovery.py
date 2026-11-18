
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


class TestFailedStepRecovery(unittest.TestCase):

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
            plan_id="recovery-test",
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

    def test_failed_step_is_retried_without_repeating_completed_step(self):
        plan = self.create_plan()

        original_tools = {
            "mock_calculator": lambda inputs: {
                "tool": "mock_calculator",
                "result": inputs["a"] + inputs["b"],
                "mode": "mock",
            },
        }

        call_counts = {"step1": 0, "step2": 0}

        def fail_second_step(inputs):
            if inputs["a"] == 2:
                call_counts["step1"] += 1
                return original_tools["mock_calculator"](inputs)

            call_counts["step2"] += 1
            raise ValueError("Temporary test failure")

        with patch(
            "workflow.executor.MOCK_TOOLS",
            {"mock_calculator": fail_second_step},
        ):
            first_result = execute_plan(plan)

        self.assertEqual(first_result.state, WorkflowState.FAILED)
        self.assertEqual(call_counts["step1"], 1)
        self.assertEqual(call_counts["step2"], 1)

        saved = checkpoint.load_checkpoint("recovery-test")

        self.assertEqual(saved["completed_steps"], ["step1"])
        self.assertEqual(saved["next_step_index"], 1)
        self.assertEqual(saved["failed_step"], "step2")

        def successful_second_attempt(inputs):
            if inputs["a"] == 2:
                call_counts["step1"] += 1
            else:
                call_counts["step2"] += 1

            return original_tools["mock_calculator"](inputs)

        with patch(
            "workflow.executor.MOCK_TOOLS",
            {"mock_calculator": successful_second_attempt},
        ):
            resumed_result = execute_plan(plan, resume=True)

        self.assertEqual(resumed_result.state, WorkflowState.SUCCEEDED)

        # Step 1 must not execute again.
        self.assertEqual(call_counts["step1"], 1)

        # Step 2 must execute again and succeed.
        self.assertEqual(call_counts["step2"], 2)

        self.assertEqual(len(resumed_result.step_results), 2)


if __name__ == "__main__":
    unittest.main()
