import threading
import time
import unittest
from unittest.mock import patch

from workflow.schemas import (
    WorkflowPlan,
    WorkflowStep,
    WorkflowState,
)
from workflow.executor import execute_plan, validate_plan


class TestWeek2Policies(unittest.TestCase):

    def test_missing_dependency_rejected(self):
        plan = WorkflowPlan(
            "missing-dependency",
            [
                WorkflowStep(
                    "s1", "mock_calculator",
                    {"a": 1, "b": 2},
                    dependencies=["unknown"],
                )
            ],
        )

        result = execute_plan(plan)
        self.assertEqual(result.state, WorkflowState.FAILED)
        self.assertIn("Missing dependency", result.error)

    def test_circular_dependency_rejected(self):
        plan = WorkflowPlan(
            "cycle",
            [
                WorkflowStep(
                    "s1", "mock_calculator",
                    {"a": 1, "b": 2},
                    dependencies=["s2"],
                ),
                WorkflowStep(
                    "s2", "mock_calculator",
                    {"a": 2, "b": 3},
                    dependencies=["s1"],
                ),
            ],
        )

        result = execute_plan(plan)
        self.assertEqual(result.state, WorkflowState.FAILED)
        self.assertIn("Circular dependency", result.error)

    def test_invalid_arguments_rejected(self):
        plan = WorkflowPlan(
            "bad-arguments",
            [
                WorkflowStep(
                    "s1", "mock_calculator",
                    {"a": 1, "unexpected": 2},
                )
            ],
        )

        result = execute_plan(plan)
        self.assertEqual(result.state, WorkflowState.FAILED)
        self.assertIn("arguments", result.error)

    def test_missing_arguments_rejected(self):
        plan = WorkflowPlan(
            "missing-arguments",
            [
                WorkflowStep(
                    "s1", "mock_calculator",
                    {"a": 1},
                )
            ],
        )

        result = execute_plan(plan)
        self.assertEqual(result.state, WorkflowState.FAILED)
        self.assertIn("Missing arguments", result.error)

    def test_wrong_permission_scope_rejected(self):
        plan = WorkflowPlan(
            "wrong-permission",
            [
                WorkflowStep(
                    "s1", "mock_calculator",
                    {"a": 1, "b": 2},
                    permission_scope="admin",
                )
            ],
        )

        result = execute_plan(plan)
        self.assertEqual(result.state, WorkflowState.FAILED)
        self.assertIn("Permission denied", result.error)

    def test_rejected_approval_does_not_execute_tool(self):
        plan = WorkflowPlan(
            "rejected",
            [
                WorkflowStep(
                    "s1", "mock_note_preview",
                    {"title": "Test", "content": "No execution"},
                    consequential=True,
                )
            ],
        )

        with patch(
            "workflow.executor.MOCK_TOOLS"
        ) as tools:
            result = execute_plan(
                plan,
                approvals={"s1": False},
            )

            tools["mock_note_preview"].assert_not_called()

        self.assertEqual(result.state, WorkflowState.FAILED)
        self.assertEqual(
            result.audit_events[-1]["event"],
            "approval_rejected",
        )

    def test_expired_approval_does_not_execute_tool(self):
        plan = WorkflowPlan(
            "expired",
            [
                WorkflowStep(
                    "s1", "mock_note_preview",
                    {"title": "Test", "content": "Expired"},
                    consequential=True,
                )
            ],
        )

        with patch(
            "workflow.executor.MOCK_TOOLS"
        ) as tools:
            result = execute_plan(
                plan,
                approvals={
                    "s1": {
                        "approved": True,
                        "expires_at": time.time() - 10,
                    }
                },
            )

            tools["mock_note_preview"].assert_not_called()

        self.assertEqual(result.state, WorkflowState.FAILED)
        self.assertEqual(
            result.audit_events[-1]["event"],
            "approval_expired",
        )

    def test_timeout_is_recorded(self):
        plan = WorkflowPlan(
            "timeout",
            [
                WorkflowStep(
                    "s1", "mock_calculator",
                    {"a": 1, "b": 2},
                    timeout_seconds=0.01,
                )
            ],
        )

        def slow_tool(inputs):
            time.sleep(0.2)
            return {"result": 3}

        with patch(
            "workflow.executor.MOCK_TOOLS",
            {"mock_calculator": slow_tool},
        ):
            result = execute_plan(plan)

        self.assertEqual(result.state, WorkflowState.FAILED)
        self.assertTrue(
            any(
                event["event"] == "step_timeout"
                for event in result.audit_events
            )
        )

    def test_idempotent_tool_can_retry(self):
        plan = WorkflowPlan(
            "retry",
            [
                WorkflowStep(
                    "s1", "mock_calculator",
                    {"a": 1, "b": 2},
                    retries=1,
                )
            ],
        )

        calls = {"count": 0}

        def sometimes_fails(inputs):
            calls["count"] += 1

            if calls["count"] == 1:
                raise ValueError("Temporary error")

            return {"result": 3}

        with patch(
            "workflow.executor.MOCK_TOOLS",
            {"mock_calculator": sometimes_fails},
        ):
            result = execute_plan(plan)

        self.assertEqual(result.state, WorkflowState.SUCCEEDED)
        self.assertEqual(calls["count"], 2)

    def test_cancellation_prevents_execution(self):
        plan = WorkflowPlan(
            "cancelled",
            [
                WorkflowStep(
                    "s1", "mock_calculator",
                    {"a": 1, "b": 2},
                )
            ],
        )

        cancel_event = threading.Event()
        cancel_event.set()

        with patch(
            "workflow.executor.MOCK_TOOLS"
        ) as tools:
            result = execute_plan(
                plan,
                cancel_event=cancel_event,
            )

            tools["mock_calculator"].assert_not_called()

        self.assertEqual(result.state, WorkflowState.CANCELLED)
        self.assertEqual(
            result.audit_events[-1]["event"],
            "cancelled",
        )


if __name__ == "__main__":
    unittest.main()
