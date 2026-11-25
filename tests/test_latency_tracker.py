"""Tests for processing-stage latency instrumentation."""

import time
import unittest

from observations.latency_tracker import LatencyTracker


class TestLatencyTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = LatencyTracker()

    def test_record_latency(self):
        self.tracker.record("reasoning", 12.5)

        report = self.tracker.get_report()

        self.assertEqual(report["reasoning"]["count"], 1)
        self.assertEqual(report["reasoning"]["average_ms"], 12.5)

    def test_measure_context_manager(self):
        with self.tracker.measure("context_builder"):
            time.sleep(0.001)

        report = self.tracker.get_report()

        self.assertEqual(report["context_builder"]["count"], 1)
        self.assertGreater(report["context_builder"]["average_ms"], 0)

    def test_multiple_measurements(self):
        self.tracker.record("capture", 10)
        self.tracker.record("capture", 20)
        self.tracker.record("capture", 30)

        report = self.tracker.get_report()["capture"]

        self.assertEqual(report["count"], 3)
        self.assertEqual(report["average_ms"], 20)
        self.assertEqual(report["min_ms"], 10)
        self.assertEqual(report["max_ms"], 30)

    def test_multiple_stages(self):
        self.tracker.record("capture", 5)
        self.tracker.record("reasoning", 15)

        report = self.tracker.get_report()

        self.assertIn("capture", report)
        self.assertIn("reasoning", report)

    def test_rejects_empty_stage_name(self):
        with self.assertRaises(ValueError):
            self.tracker.record("", 10)

    def test_rejects_negative_duration(self):
        with self.assertRaises(ValueError):
            self.tracker.record("reasoning", -5)

    def test_rejects_non_numeric_duration(self):
        with self.assertRaises(TypeError):
            self.tracker.record("reasoning", "fast")

    def test_clear_measurements(self):
        self.tracker.record("capture", 10)
        self.tracker.clear()

        self.assertEqual(self.tracker.get_report(), {})


if __name__ == "__main__":
    unittest.main()