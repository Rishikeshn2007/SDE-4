import unittest

from workflow.schemas import WorkflowPlan, WorkflowStep
from workflow.executor import validate_plan


class TestSchemas(unittest.TestCase):

    def test_valid_plan(self):
        plan = WorkflowPlan(
            plan_id="valid-plan",
            steps=[
                WorkflowStep(
                    step_id="s1",
                    tool_name="mock_calculator",
                    inputs={"a": 1, "b": 2},
                )
            ],
        )

        validate_plan(plan)

    def test_duplicate_step_ids_rejected(self):
        plan = WorkflowPlan(
            plan_id="invalid-plan",
            steps=[
                WorkflowStep("s1", "mock_calculator"),
                WorkflowStep("s1", "mock_note_preview"),
            ],
        )

        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_empty_plan_rejected(self):
        plan = WorkflowPlan(
            plan_id="empty-plan",
            steps=[],
        )

        with self.assertRaises(ValueError):
            validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
class TestAdditionalInvalidPlans(unittest.TestCase):

    def test_blank_plan_id_rejected(self):
        plan = WorkflowPlan(
            plan_id=" ",
            steps=[WorkflowStep("s1", "mock_calculator")]
        )
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_blank_step_id_rejected(self):
        plan = WorkflowPlan(
            plan_id="valid",
            steps=[WorkflowStep(" ", "mock_calculator")]
        )
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_invalid_inputs_type_rejected(self):
        plan = WorkflowPlan(
            plan_id="valid",
            steps=[
                WorkflowStep(
                    "s1",
                    "mock_calculator",
                    inputs=["not", "a", "dictionary"]
                )
            ],
        )
        with self.assertRaises(ValueError):
            validate_plan(plan)
