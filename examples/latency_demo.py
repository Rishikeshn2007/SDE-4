"""Demonstrate processing-stage latency reporting."""

import json
import time

from observations.latency_tracker import LatencyTracker


def run_demo():
    tracker = LatencyTracker()

    with tracker.measure("capture"):
        time.sleep(0.01)

    with tracker.measure("context_builder"):
        time.sleep(0.02)

    with tracker.measure("reasoning"):
        time.sleep(0.015)

    report = tracker.get_report()

    print("========== LATENCY REPORT ==========")
    print(json.dumps(report, indent=4))
    print("====================================")

    return report


if __name__ == "__main__":
    run_demo()