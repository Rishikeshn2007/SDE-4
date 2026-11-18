
import unittest
import tempfile
from pathlib import Path

import workflow.checkpoint as checkpoint


class TestCheckpoint(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_dir = checkpoint.CHECKPOINT_DIR
        checkpoint.CHECKPOINT_DIR = Path(self.temp_dir.name)

    def tearDown(self):
        checkpoint.CHECKPOINT_DIR = self.original_dir
        self.temp_dir.cleanup()

    def test_save_checkpoint(self):
        result = checkpoint.save_checkpoint(
            plan_id="test-1",
            completed_steps=["s1"],
            step_results=[
                {"step_id": "s1", "output": {"result": 5}}
            ],
            next_step_index=1,
            state="paused",
        )

        self.assertTrue(result.exists())

    def test_load_checkpoint(self):
        checkpoint.save_checkpoint(
            plan_id="test-2",
            completed_steps=["s1"],
            step_results=[],
            next_step_index=1,
            state="paused",
        )

        result = checkpoint.load_checkpoint("test-2")

        self.assertEqual(result["plan_id"], "test-2")
        self.assertEqual(result["completed_steps"], ["s1"])
        self.assertEqual(result["next_step_index"], 1)

    def test_missing_checkpoint(self):
        with self.assertRaises(FileNotFoundError):
            checkpoint.load_checkpoint("missing")


if __name__ == "__main__":
    unittest.main()
