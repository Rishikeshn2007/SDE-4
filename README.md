# SDE-4 - Context and Reasoning Voicebot

## Overview
A context-aware reasoning project that uses synthetic context, source-grounded answers, consent controls, privacy safeguards, and confirmation-gated workflow proposals.

## Week 4 Deliverables
- Golden reasoning tests for evidence, source references, no-evidence cases, and prompt injection.
- Privacy redaction for recognized emails, tokens, and secret assignments.
- Consent withdrawal and pending-observation clearing.
- Per-stage latency tracking.
- Prompt-version metadata.
- Data-handling and retention documentation.
- Automated backend tests and frontend build through GitHub Actions.

## Project Structure
- `adapters/` - Synthetic capture and vision adapters.
- `backend/` - Flask API.
- `docs/` - Data-handling documentation.
- `examples/` - Integration, latency, and failure demonstrations.
- `observations/` - Consent, latency, and privacy utilities.
- `prompts/` - Prompt version tracking.
- `reasoning/` - Grounded and mock reasoning.
- `schemas/` - Context and workflow schemas.
- `tests/` - Unit, integration, and golden tests.
- `frontend/` - React and TypeScript application.

## Setup

Install Python dependencies:

    python -m pip install -r requirements.txt

Install frontend dependencies:

    npm.cmd ci

## Demonstrations

Normal integration:

    python -m examples.week3_demo

No-evidence failure case:

    python -m examples.week4_failure_demo

Latency demonstration:

    python -m examples.latency_demo

The latency demonstration uses artificial delays. Its measurements are illustrative, not production benchmarks.

## Backend Tests

Run all backend tests:

    python -m unittest discover -s tests -v

Run golden tests separately:

    python -m unittest tests.golden.test_golden_reasoning -v

## Frontend Build

    npm.cmd run build

## Privacy and Safety
- Capture is disabled by default.
- The capture adapter accepts synthetic frames only.
- Consent withdrawal disables capture and clears pending observations held by the consent manager.
- Redaction is pattern-based and cannot guarantee detection of every secret.
- Context is treated as untrusted input.
- Workflow proposals require explicit confirmation.
- Approval does not execute a real-world action.

See `docs/DATA_HANDLING.md` for retention behavior and limitations.

See `docs/LATENCY_REPORT.md` for the recorded per-stage latency demonstration
and its measurement limitations.

## Known Limitations
- No real screen capture is implemented.
- Reasoning and workflow demonstrations use mock components.
- In-memory clearing is not secure erasure.
- Prompt metadata is not stored in a persistent audit database.
- Latency measurements are illustrative.
- Production deployment requires a separate security and privacy review.

## Local Verification - 25 November 2026
- Backend test suite: 132 tests passed.
- Golden tests: 9 passed.
- Latency demonstration: completed.
- Week 3 integration demonstration: completed.
- Frontend installation: completed, zero reported vulnerabilities.
- Frontend production build: passed.

These are local results. GitHub Actions must also pass on the submitted branch.
