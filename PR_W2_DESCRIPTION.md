# SDE-4: Week 2 – Speech-to-Text Orchestration, Ordering & De-duplication, Retries & Preprocessing (W2)

**Student:** Suresh V Patil  
**Team:** SDE 4  
**Workstream:** W2 – Speech-to-text Orchestration & Resiliency (Days 8–14)  
**Project Folder:** `projects/sde-4-voicebot/` | **Branch:** `suresh`  

---

## Overview

Week 2 connects incoming audio chunks to a provider adapter and produces clean, ordered transcript events with safe failure handling, genuine timeout enforcement, duplicate suppression, interim/final reconciliation, anti-aliased sinc-FIR downsampling, RMS normalization, and stateful voice activity detection (VAD).

---

## Deliverables Completed

- [x] **D8–9 (Transcription Orchestrator):**
  - Implemented `TranscriptionOrchestrator` and `TranscriptionResult` in [`src/sde4_stt/orchestrator.py`](src/sde4_stt/orchestrator.py).
  - Handles the end-to-end pipeline: session management, audio preprocessing, retry-wrapped chunk delivery, event stream processing, and statistical aggregation.
  - Hardened exception boundaries so no uncaught provider exceptions leak to callers.

- [x] **D10–11 (Ordering, De-duplication & Interim/Final Reconciliation):**
  - Built `EventDeduplicator` in [`src/sde4_stt/dedup.py`](src/sde4_stt/dedup.py).
  - Suppresses duplicate events by tracking processed `event_id`s.
  - Reconciles interim hypotheses into final committed segments, guaranteeing monotonic ordering and timeline continuity.

- [x] **D12–13 (Timeouts, Bounded Retries & Error Normalization):**
  - Built `RetryConfig`, `NormalizedError`, and `RetryableAdapter` in [`src/sde4_stt/retry.py`](src/sde4_stt/retry.py).
  - Multi-threaded timeout enforcement with `ThreadPoolExecutor` and cumulative budget tracking.
  - Exponential backoff with configurable base, max delay, and jitter.
  - Normalizes heterogeneous provider exceptions into standard `TranscriptError` objects.

- [x] **D12–13 (Audio Preprocessing & Reusable VAD):**
  - Implemented `AudioPreprocessor` in [`src/sde4_stt/preprocessing.py`](src/sde4_stt/preprocessing.py) with anti-aliasing sinc-FIR low-pass filter downsampling (e.g. 48 kHz -> 16 kHz), channel conversion (stereo <-> mono), and clipping-free RMS gain normalization.
  - Implemented reusable stateful `VoiceActivityDetector` in [`src/sde4_stt/vad.py`](src/sde4_stt/vad.py) with configurable energy thresholds, speech/silence duration smoothing, and adaptive background noise estimation.

- [x] **D14 (Contract Tests & Synthetic Demo):**
  - Contract test suites covering orchestrator, deduplicator, retry wrapper, preprocessor, and VAD.
  - End-to-end runnable demonstration in [`demo_w2.py`](demo_w2.py) executing a synthetic 48 kHz fixture preprocessed and transcribed with zero API keys.

---

## Acceptance Criteria Checklist

- [x] **Chunk to transcript events works end to end in mock mode:** Verified via `TranscriptionOrchestrator` and `demo_w2.py`.
- [x] **Out-of-order and duplicate segments handled correctly:** Reconciled into sorted final utterances.
- [x] **Timeouts and bounded retries work:** Provider errors normalized into `TranscriptError` without crashing the pipeline.
- [x] **Resampling and normalization tested:** Anti-aliasing sinc FIR filter and RMS normalization fully covered.
- [x] **Contract tests cover the adapter and events:** Default path requires no real provider or API key.
- [x] **No duplicate schema definitions:** Authoritative W1 schemas strictly reused from `academia_audio.schemas`.
- [x] **No recordings or secrets committed:** Clean git tree without committed audio recordings or virtual environments.

---

## Test Suite Output (Clean Clone, 199 Passed)

Executed in a clean virtual environment with `pip install -e ".[dev]"` (no `SpeechRecognition`):

```text
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\sures\Desktop\SDE-4
configfile: pyproject.toml
testpaths: tests
collected 199 items

tests/test_accumulator.py .....                                          [  2%]
tests/test_adapters.py ...................                               [ 12%]
tests/test_cli.py .....                                                  [ 14%]
tests/test_dedup.py ...........                                          [ 20%]
tests/test_orchestrator.py .....................                         [ 30%]
tests/test_preprocessing.py ........................                     [ 42%]
tests/test_retry.py .........................                            [ 55%]
tests/test_schemas.py .................................................. [ 80%]
.....                                                                    [ 82%]
tests/test_source_and_chunker.py .......................                 [ 94%]
tests/test_vad.py ...........                                            [100%]

============================= 199 passed in 0.70s =============================
```
