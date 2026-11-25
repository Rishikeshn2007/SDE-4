"""Measure processing-stage latency without storing sensitive data."""

from contextlib import contextmanager
from time import perf_counter


class LatencyTracker:
    """Record elapsed time for individual processing stages."""

    def __init__(self):
        self._measurements = {}

    @contextmanager
    def measure(self, stage_name):
        """Measure execution time for a named stage."""

        if not isinstance(stage_name, str) or not stage_name.strip():
            raise ValueError("Stage name must be a non-empty string")

        start_time = perf_counter()

        try:
            yield
        finally:
            elapsed_ms = (perf_counter() - start_time) * 1000

            self._measurements.setdefault(
                stage_name, []
            ).append(elapsed_ms)

    def record(self, stage_name, duration_ms):
        """Record an externally measured duration."""

        if not isinstance(stage_name, str) or not stage_name.strip():
            raise ValueError("Stage name must be a non-empty string")

        if isinstance(duration_ms, bool) or not isinstance(
            duration_ms, (int, float)
        ):
            raise TypeError("Duration must be numeric")

        if duration_ms < 0:
            raise ValueError("Duration cannot be negative")

        self._measurements.setdefault(
            stage_name, []
        ).append(float(duration_ms))

    def get_report(self):
        """Return count, average, minimum, and maximum per stage."""

        report = {}

        for stage_name, durations in self._measurements.items():
            report[stage_name] = {
                "count": len(durations),
                "average_ms": round(
                    sum(durations) / len(durations), 3
                ),
                "min_ms": round(min(durations), 3),
                "max_ms": round(max(durations), 3),
            }

        return report

    def clear(self):
        """Clear all recorded measurements."""

        self._measurements.clear()