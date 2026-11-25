# Data Handling and Privacy

## Purpose
This document describes data handling during development and testing. This project is not a production-certified privacy or security system.

## Data Types
The project processes synthetic frame content, questions, context observations, source references, prompt metadata, test measurements, and audio submitted to the local transcription endpoint with the required consent header.

Never commit real personal screenshots, recordings, passwords, API keys, or access tokens.

## Processing and Redaction
- Capture is disabled by default.
- The capture adapter accepts synthetic frames only.
- Capture requires explicit opt-in.
- The redactor masks recognized email addresses, common tokens, and recognized secret assignments.
- Covered reasoning and LLM paths apply redaction to relevant inputs and outputs.
- Context is treated as untrusted input.
- Prompt-injection checks cover selected patterns.

Redaction is pattern-based and cannot detect every possible secret.

## Consent and Withdrawal
The consent manager starts disabled, rejects observations without consent, disables capture on withdrawal, and clears its pending in-memory observations.

This does not guarantee deletion from external services, operating-system buffers, logs, or persistent storage.

## Retention
| Data | Handling |
|---|---|
| Synthetic frames | Used during processing and demonstrations |
| Pending observations | Held in the active consent manager's memory |
| Observations after withdrawal | Cleared from that manager |
| Observation age | Default builder filter is 86,400 seconds (24 hours) |
| Prompt metadata | Held in an in-memory registry |
| Latency measurements | Held in the tracker until cleared or the process ends |
| Test output | May remain in terminal or CI logs according to environment settings |
| Real personal data | Not permitted in repository test fixtures |

The 24-hour setting is an observation-age filtering rule, not an automatic deletion timer. Clearing Python collections is not secure memory erasure. The project has no universal persistent-data deletion mechanism.

## Audio and Logging
The local speech endpoint requires its audio-consent header and enforces a request-size limit. This project does not guarantee that every transcript, temporary buffer, log, or external component is automatically redacted or securely erased.

Do not log raw passwords, API keys, or tokens. Use synthetic test values.

## Latency
The latency tracker records elapsed time by processing stage. The demonstration deliberately uses artificial delays. Its results are illustrative, not production benchmarks.

## Security Limitations
- Pattern-based redaction can miss sensitive values.
- Not every logging or transcription path is guaranteed to redact data.
- Prompt metadata is not a persistent audit history.
- Consent withdrawal does not guarantee secure erasure everywhere.
- Prompt-injection tests cover selected cases, not every possible attack.
- Mock components do not prove production integration security.

Production use requires a separate privacy, security, and threat-model review.

## Tests
Run from the project directory:

    python -m unittest discover -s tests -v

Tests cover redaction, consent withdrawal, prompt injection, golden reasoning, prompt versions, and latency tracking.

## Review
Update this document whenever data collection, processing, retention, redaction, or consent behavior changes.
