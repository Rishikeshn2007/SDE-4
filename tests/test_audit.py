
import unittest
import tempfile
from pathlib import Path

import workflow.audit as audit


class TestAudit(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_dir = audit.AUDIT_DIR
        audit.AUDIT_DIR = Path(self.temp_dir.name)

    def tearDown(self):
        audit.AUDIT_DIR = self.original_dir
        self.temp_dir.cleanup()

    def test_record_event(self):
        events = []

        result = audit.record_event(
            events,
            "step_succeeded",
            "s1",
            "Step completed",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(result["event"], "step_succeeded")
        self.assertEqual(result["step_id"], "s1")
        self.assertIn("timestamp", result)

    def test_save_and_load_audit_log(self):
        events = [
            {
                "event": "step_succeeded",
                "step_id": "s1",
                "message": "Completed",
                "timestamp": 12345,
            }
        ]

        audit.save_audit_log("test-1", events)
        loaded = audit.load_audit_log("test-1")

        self.assertEqual(loaded, events)

    def test_missing_audit_log(self):
        with self.assertRaises(FileNotFoundError):
            audit.load_audit_log("missing")


if __name__ == "__main__":
    unittest.main()
