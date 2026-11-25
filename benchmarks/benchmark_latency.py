"""
Reproducible STT Latency Benchmarking Utility (Week 4, Day 22–24).

Measures transcription request latency under controlled synthetic audio fixtures.
Operates 100% offline using the deterministic mock provider by default.
Supports optional real-provider benchmarking when explicitly specified.

Calculates:
- Total iterations
- Minimum latency (ms)
- Maximum latency (ms)
- Mean latency (ms)
- Median latency (P50, ms)
- 95th percentile latency (P95, ms)
- 99th percentile latency (P99, ms)
- Standard deviation (ms)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repository root and src directory are on sys.path when executed directly
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from academia_audio.mock_source import MockMicrophone
from academia_audio.schemas import AudioFormat

from sde4_stt.adapters.base import BaseTranscriberAdapter
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.orchestrator import TranscriptionOrchestrator
from sde4_stt.preprocessing import AudioPreprocessor


@dataclass
class LatencyBenchmarkConfig:
    """Benchmark configuration parameters."""
    provider: str = "mock"
    iterations: int = 50
    warmup_iterations: int = 5
    fixture_duration_s: float = 2.0
    fixture_chunk_ms: int = 100
    sample_rate: int = 16000
    channels: int = 1
    preprocess: bool = True
    output_dir: str = "benchmarks/results"


@dataclass
class LatencyMetrics:
    """Calculated statistical metrics for latency."""
    iterations: int
    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    std_dev_ms: float
    individual_latencies_ms: List[float] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    """Complete serialized benchmark result."""
    timestamp_utc: str
    config: Dict[str, Any]
    fixture_info: Dict[str, Any]
    metrics: Dict[str, Any]


def calculate_percentile(sorted_values: List[float], percentile: float) -> float:
    """Calculate the given percentile (0.0 to 100.0) from a sorted list of numbers."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return d0 + d1


def compute_metrics(latencies_ms: List[float]) -> LatencyMetrics:
    """Calculate statistical distribution metrics from measured latency values."""
    if not latencies_ms:
        return LatencyMetrics(
            iterations=0,
            min_ms=0.0,
            max_ms=0.0,
            mean_ms=0.0,
            median_ms=0.0,
            p95_ms=0.0,
            p99_ms=0.0,
            std_dev_ms=0.0,
            individual_latencies_ms=[],
        )

    n = len(latencies_ms)
    sorted_lats = sorted(latencies_ms)
    min_val = round(sorted_lats[0], 3)
    max_val = round(sorted_lats[-1], 3)
    mean_val = round(sum(sorted_lats) / n, 3)
    median_val = round(calculate_percentile(sorted_lats, 50.0), 3)
    p95_val = round(calculate_percentile(sorted_lats, 95.0), 3)
    p99_val = round(calculate_percentile(sorted_lats, 99.0), 3)

    variance = sum((x - mean_val) ** 2 for x in sorted_lats) / n if n > 1 else 0.0
    std_dev_val = round(math.sqrt(variance), 3)

    return LatencyMetrics(
        iterations=n,
        min_ms=min_val,
        max_ms=max_val,
        mean_ms=mean_val,
        median_ms=median_val,
        p95_ms=p95_val,
        p99_ms=p99_val,
        std_dev_ms=std_dev_val,
        individual_latencies_ms=[round(x, 3) for x in latencies_ms],
    )


def build_adapter(provider: str) -> BaseTranscriberAdapter:
    """Factory creating the requested provider adapter."""
    if provider == "mock":
        return FakeTranscriber(
            canned_transcript="benchmark synthetic speech audio utterance",
            fixed_confidence=0.98,
        )
    elif provider == "real":
        try:
            from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber
            return RealSpeechTranscriber()
        except ImportError as exc:
            raise RuntimeError(
                f"Real provider dependencies not available: {exc}. "
                "Install with `pip install -e '.[google-stt]'`."
            )
    else:
        raise ValueError(f"Unknown provider: '{provider}'. Supported: 'mock', 'real'.")


def run_latency_benchmark(config: LatencyBenchmarkConfig) -> BenchmarkReport:
    """Execute latency benchmark with the given configuration."""
    fmt = AudioFormat(sample_rate=config.sample_rate, channels=config.channels)
    mic = MockMicrophone(
        fmt=fmt,
        duration_s=config.fixture_duration_s,
        chunk_ms=config.fixture_chunk_ms,
        frequency_hz=440.0,
        amplitude=0.5,
    )

    # Pre-generate immutable synthetic chunks
    fixture_chunks = list(mic.stream())
    total_bytes = sum(len(c.data) for c in fixture_chunks)
    fixture_info = {
        "fixture_id": f"synthetic_sine_{config.sample_rate}hz_{config.fixture_duration_s}s",
        "num_chunks": len(fixture_chunks),
        "chunk_ms": config.fixture_chunk_ms,
        "sample_rate": config.sample_rate,
        "channels": config.channels,
        "duration_s": config.fixture_duration_s,
        "total_bytes": total_bytes,
    }

    preprocessor = (
        AudioPreprocessor(target_sample_rate=config.sample_rate, normalize_audio=True)
        if config.preprocess
        else None
    )

    # Warmup phase (not timed)
    for w in range(config.warmup_iterations):
        adapter = build_adapter(config.provider)
        orch = TranscriptionOrchestrator(adapter=adapter, preprocessor=preprocessor)
        orch.transcribe(fixture_chunks, session_id=f"warmup_{w}")

    # Timed benchmark iterations
    latencies_ms: List[float] = []
    for i in range(config.iterations):
        adapter = build_adapter(config.provider)
        orch = TranscriptionOrchestrator(adapter=adapter, preprocessor=preprocessor)

        t_start = time.perf_counter()
        result = orch.transcribe(fixture_chunks, session_id=f"bench_sess_{i:04d}")
        t_elapsed = (time.perf_counter() - t_start) * 1000.0

        if result.has_errors:
            # Record error if any
            pass
        latencies_ms.append(t_elapsed)

    metrics = compute_metrics(latencies_ms)

    timestamp_str = datetime.now(timezone.utc).isoformat()
    report = BenchmarkReport(
        timestamp_utc=timestamp_str,
        config=asdict(config),
        fixture_info=fixture_info,
        metrics=asdict(metrics),
    )

    # Save to output directory
    out_dir = Path(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    file_path = out_dir / f"latency_{config.provider}_{date_tag}.json"
    latest_path = out_dir / f"latency_{config.provider}_latest.json"

    report_dict = asdict(report)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)

    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)

    return report


def print_summary_table(report: BenchmarkReport) -> None:
    """Print clean terminal summary of benchmark results."""
    cfg = report.config
    m = report.metrics
    fix = report.fixture_info

    sep = "=" * 65
    print("\n" + sep)
    print(" SDE-4 SPEECH-TO-TEXT LATENCY BENCHMARK REPORT")
    print(sep)
    print(f" Timestamp (UTC):   {report.timestamp_utc}")
    print(f" Provider:          {cfg['provider']}")
    print(f" Iterations:        {m['iterations']} (Warmup: {cfg['warmup_iterations']})")
    print(f" Preprocessing:     {cfg['preprocess']}")
    print(f" Audio Fixture:     {fix['fixture_id']} ({fix['duration_s']}s, {fix['num_chunks']} chunks)")
    print(sep)
    print(" Latency Statistics (ms):")
    print(f"   * Min:           {m['min_ms']:>8.3f} ms")
    print(f"   * Mean:          {m['mean_ms']:>8.3f} ms")
    print(f"   * Median (P50):  {m['median_ms']:>8.3f} ms")
    print(f"   * P95:           {m['p95_ms']:>8.3f} ms")
    print(f"   * P99:           {m['p99_ms']:>8.3f} ms")
    print(f"   * Max:           {m['max_ms']:>8.3f} ms")
    print(f"   * Std Dev:       {m['std_dev_ms']:>8.3f} ms")
    print(sep + "\n")


def main() -> int:
    """CLI entrypoint for benchmark utility."""
    parser = argparse.ArgumentParser(description="SDE-4 STT Latency Benchmark Utility")
    parser.add_argument(
        "--provider",
        choices=["mock", "real"],
        default="mock",
        help="Provider adapter to benchmark (default: 'mock')",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=50,
        help="Number of timed benchmark iterations (default: 50)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=5,
        help="Number of untimed warmup iterations (default: 5)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Synthetic audio fixture duration in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--chunk-ms",
        type=int,
        default=100,
        help="Audio chunk duration in milliseconds (default: 100)",
    )
    parser.add_argument(
        "--no-preprocess",
        action="store_true",
        help="Disable audio preprocessing in the orchestrator pipeline",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks/results",
        help="Directory where benchmark JSON results are stored",
    )

    args = parser.parse_args()

    config = LatencyBenchmarkConfig(
        provider=args.provider,
        iterations=args.iterations,
        warmup_iterations=args.warmup,
        fixture_duration_s=args.duration,
        fixture_chunk_ms=args.chunk_ms,
        preprocess=not args.no_preprocess,
        output_dir=args.output_dir,
    )

    print(f"Running STT Latency Benchmark ({config.provider} provider, {config.iterations} iterations)...")
    report = run_latency_benchmark(config)
    print_summary_table(report)
    print(f"Results stored in '{config.output_dir}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
