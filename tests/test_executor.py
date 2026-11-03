import unittest

from workflow.schemas import (
    WorkflowPlan,
    WorkflowStep,
    WorkflowState,
)
from workflow.executor import execute_plan


class TestExecutor(unittest.TestCase):

    def test_mock_calculator(self):
        plan = WorkflowPlan(
            plan_id="test-1",
            steps=[
                WorkflowStep(
                    step_id="s1",
                    tool_name="mock_calculator",
                    inputs={"a": 2, "b": 3},
                )
            ],
        )

        result = execute_plan(plan)

        self.assertEqual(
            result.state, WorkflowState.SUCCEEDED
        )
        self.assertEqual(
            result.step_results[0]["output"]["result"], 5
        )

    def test_unknown_tool_rejected(self):
        plan = WorkflowPlan(
            plan_id="test-2",
            steps=[
                WorkflowStep(
                    step_id="s1",
                    tool_name="unknown_tool",
                )
            ],
        )

        result = execute_plan(plan)

        self.assertEqual(result.state, WorkflowState.FAILED)

    def test_consequential_step_waits_for_approval(self):
        plan = WorkflowPlan(
            plan_id="test-3",
            steps=[
                WorkflowStep(
                    step_id="s1",
                    tool_name="mock_calculator",
                    inputs={"a": 2, "b": 3},
                ),
                WorkflowStep(
                    step_id="s2",
                    tool_name="mock_note_preview",
                    inputs={
                        "title": "Test",
                        "content": "Simulation",
                    },
                    consequential=True,
                ),
            ],
        )

        result = execute_plan(plan)

        self.assertEqual(
            result.state,
            WorkflowState.AWAITING_APPROVAL,
        )
        self.assertEqual(len(result.step_results), 1)
        self.assertEqual(
            result.approval_request.step_id, "s2"
        )

    def test_explicit_approval_allows_mock_execution(self):
        plan = WorkflowPlan(
            plan_id="test-4",
            steps=[
                WorkflowStep(
                    step_id="s1",
                    tool_name="mock_note_preview",
                    inputs={
                        "title": "Test",
                        "content": "Approved simulation",
                    },
                    consequential=True,
                )
            ],
        )

        result = execute_plan(
            plan,
            approvals={"s1": True},
        )

        self.assertEqual(
            result.state, WorkflowState.SUCCEEDED
        )


if __name__ == "__main__":
    unittest.main()