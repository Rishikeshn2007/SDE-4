# SDE-4: Speech-to-Text Pipeline – Complete W1 & W2 Implementation

**Student:** Suresh V Patil  
**Team:** SDE 4  
**Workstream:** W1 (Foundation) & W2 (Orchestration & Resiliency)  
**Branch:** `suresh` -> `main`  
**PR URL:** https://github.com/Rishikeshn2007/SDE-4/pull/7  

---

## 1. Summary of Work

This Pull Request delivers the complete Speech-to-Text (STT) workstream for the Academia AI Voice Co-Pilot:
- **Week 1:** Foundational data contracts, provider-neutral adapter interface, deterministic mock transcriber, segment accumulation, and clean dependency isolation.
- **Week 2:** Chunk-to-provider orchestration, event ordering and deduplication, interim/final reconciliation, bounded retries with genuine timeout enforcement, audio preprocessing (sinc-FIR downsampling, RMS normalization), and stateful Voice Activity Detection (VAD).

---

## 2. Week 1 Deliverables & Review Fixes

### Core Architecture
- **Strict Data Contracts (`academia_audio.schemas`, `src/sde4_stt/schemas/transcript.py`):**
  - Authoritative audio contracts (`AudioChunk`, `AudioFormat`, `AudioError`, `AudioErrorCode`).
  - Strict Pydantic V2 transcript contracts (`TranscriptSegment`, `WordTiming`, `TranscriptError`, `TranscriptEvent`, `TranscriptEventType`) with timestamp ordering and BCP-47 language validation.
- **Provider-Neutral Adapter Interface (`src/sde4_stt/adapters/base.py`):**
  - Abstract base contract enforcing session lifecycle: `start_session` -> `process_chunk` -> `finish_session`.
- **Deterministic Fake Transcriber (`src/sde4_stt/adapters/fake_transcriber.py`):**
  - Zero-cost mock engine supporting canned scripts, chunk hashing, and simulated error injection without any API keys or network access.
- **Segment Accumulation & Live Testing:**
  - `SegmentAccumulator` (`src/sde4_stt/accumulator.py`) assembling ordered final utterances.
  - Interactive live mic script (`manual_text.py`) and mock demo (`demo_stt.py`).

### Week 1 Code Review Fixes Implemented
- [x] **Optional Real Provider:** `speech_recognition` is lazily imported inside `RealSpeechTranscriber.__init__()` and raises a clear `ImportError` if invoked without the optional package.
- [x] **Clean Adapters Export:** `src/sde4_stt/adapters/__init__.py` strictly exports *only* `BaseTranscriberAdapter` and `FakeTranscriber`.
- [x] **Isolated Dependencies in `pyproject.toml`:** `SpeechRecognition` and `sounddevice` are isolated under `[project.optional-dependencies]` as `google-stt`.
- [x] **Single `AudioChunk` Schema:** Removed duplicate `schemas/audio.py` and reused canonical W1 `AudioChunk` from `academia_audio.schemas`.
- [x] **Git Cleanup:** Removed `.venv-offline-test/` binaries from git tracking and added `.venv*` to `.gitignore`.

---

## 3. Week 2 Deliverables Completed

### D8–9: Transcription Orchestrator (`src/sde4_stt/orchestrator.py`)
- Coordinates the complete chunk-to-transcript pipeline.
- Returns structured `TranscriptionResult` containing ordered segments, concatenated text, execution timings, duplicate suppression counts, and reconciled interim counts.
- Exception boundaries guarantee no raw provider exceptions crash the pipeline.

### D10–11: Ordering, De-duplication & Reconciliation (`src/sde4_stt/dedup.py`)
- Built `EventDeduplicator` tracking processed `event_id`s to eliminate redundant events.
- Reconciles non-final `INTERIM` hypotheses into immutable `FINAL` segments with strict chronological monotonicity.

### D12–13: Timeouts, Bounded Retries & Error Normalization (`src/sde4_stt/retry.py`)
- `RetryConfig`, `NormalizedError`, and `RetryableAdapter`.
- Thread-safe timeout enforcement using `ThreadPoolExecutor` with cumulative session budget tracking.
- Exponential backoff retry loop with configurable jitter and max attempts.
- Normalizes third-party exceptions into typed `TranscriptError` models.

### D12–13: Audio Preprocessing & Reusable VAD (`src/sde4_stt/preprocessing.py`, `src/sde4_stt/vad.py`)
- **Audio Preprocessor:** Anti-aliasing sinc-FIR low-pass filter downsampling (e.g. 48 kHz -> 16 kHz), channel conversion (stereo <-> mono), and clipping-free RMS gain normalization.
- **Voice Activity Detector:** Stateful `VoiceActivityDetector` tracking speech onset, silence trailing windows, and adaptive background noise estimation.

### D14: Synthetic Demo & Contract Tests (`demo_w2.py`, `tests/`)
- End-to-end runnable demo (`demo_w2.py`) executing a synthetic 48 kHz fixture preprocessed and transcribed with zero API keys.
- Comprehensive contract test suites verifying all W1 and W2 components.

---

## 4. Acceptance Criteria Checklist

- [x] **Chunk to transcript events works end to end in mock mode:** Verified via `TranscriptionOrchestrator`, `demo_stt.py`, and `demo_w2.py`.
- [x] **Out-of-order and duplicate segments handled correctly:** Reconciled into sorted final utterances.
- [x] **Timeouts and bounded retries work:** Provider errors normalized into `TranscriptError` without crashing the pipeline.
- [x] **Resampling and normalization tested:** Anti-aliasing sinc-FIR filter and RMS normalization fully covered.
- [x] **Contract tests cover the adapter and events:** Default path requires no real provider or API key.
- [x] **No duplicate schema definitions:** Authoritative W1 schemas strictly reused from `academia_audio.schemas`.
- [x] **No recordings or secrets committed:** Clean git tree with zero audio artifacts or committed virtual environments.

---

## 5. Automated Test Suite Results (199 Passed)

Executed in a clean virtual environment with `pip install -e ".[dev]"` (no `SpeechRecognition` installed):

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
