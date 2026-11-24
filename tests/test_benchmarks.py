"""
Tests for Latency Benchmark Utility (Week 4, Day 22–24).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from benchmarks.benchmark_latency import (
    LatencyBenchmarkConfig,
    calculate_percentile,
    compute_metrics,
    run_latency_benchmark,
)


def test_calculate_percentile():
    """Verify percentile calculation on known sample data."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert calculate_percentile(values, 0.0) == 10.0
    assert calculate_percentile(values, 50.0) == 30.0
    assert calculate_percentile(values, 100.0) == 50.0
    assert calculate_percentile([], 50.0) == 0.0


def test_compute_metrics():
    """Verify statistical metrics calculation."""
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
    metrics = compute_metrics(latencies)
    assert metrics.iterations == 5
    assert metrics.min_ms == 10.0
    assert metrics.max_ms == 50.0
    assert metrics.mean_ms == 30.0
    assert metrics.median_ms == 30.0
    assert len(metrics.individual_latencies_ms) == 5


def test_run_latency_benchmark_synthetic_offline():
    """Verify benchmark execution runs offline and creates valid JSON report."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = LatencyBenchmarkConfig(
            provider="mock",
            iterations=3,
            warmup_iterations=1,
            fixture_duration_s=0.5,
            fixture_chunk_ms=100,
            output_dir=tmp_dir,
        )
        report = run_latency_benchmark(config)

        assert report.config["provider"] == "mock"
        assert report.metrics["iterations"] == 3
        assert report.metrics["min_ms"] > 0
        assert report.metrics["max_ms"] >= report.metrics["min_ms"]
        assert report.fixture_info["num_chunks"] == 5

        # Check saved files
        files = list(Path(tmp_dir).glob("*.json"))
        assert len(files) >= 2  # timestamped and latest
