import unittest

from workflow.schemas import WorkflowState
from workflow.state_machine import transition


class TestStateMachine(unittest.TestCase):

    def test_valid_transition(self):
        self.assertEqual(
            transition(
                WorkflowState.DRAFT,
                WorkflowState.RUNNING,
            ),
            WorkflowState.RUNNING,
        )

    def test_illegal_transition(self):
        with self.assertRaises(ValueError):
            transition(
                WorkflowState.SUCCEEDED,
                WorkflowState.RUNNING,
            )


if __name__ == "__main__":
    unittest.main()