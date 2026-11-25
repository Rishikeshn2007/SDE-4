# Week 4 Latency Report

## Measurement method

The latency tracker measures elapsed time for individual processing stages
using Python's high-resolution performance counter.

The demonstration measures three stages: capture, context building, and
reasoning. Each stage was measured once in this run.

## Recorded results

Environment: Windows 11, local development run
Date: 25 November 2026
Command: `python -m examples.latency_demo`

| Stage | Count | Average (ms) | Minimum (ms) | Maximum (ms) |
|---|---:|---:|---:|---:|
| Capture | 1 | 11.905 | 11.905 | 11.905 |
| Context builder | 1 | 24.223 | 24.223 | 24.223 |
| Reasoning | 1 | 19.745 | 19.745 | 19.745 |

## Interpretation and limitations

The demonstration deliberately inserts artificial delays to exercise the
latency tracker. These values verify that per-stage measurements are
collected and reported; they are not representative production benchmarks
or measurements of actual end-to-end application performance.

Only one measurement was recorded per stage in this run. The average,
minimum, and maximum are therefore identical for each stage.

The tracker stores measurements in memory and can clear them with its
`clear()` method. It does not persist a performance history.

## Reproduction

From the project directory, run:

    python -m examples.latency_demo
