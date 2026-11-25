# SDE-4: Week 1 – Speech-to-Text Foundation & Core Adapter Integration (W1)

**Student:** Suresh V Patil  
**Team:** SDE 4  
**Workstream:** W1 – Speech-to-text Foundation (Days 1–7) & Review Fixes  
**Project Folder:** `projects/sde-4-voicebot/` | **Branch:** `suresh`  

---

## Overview

Week 1 delivers the foundational speech-to-text architecture: strict audio/transcript data contracts, an extensible provider-neutral adapter interface, a zero-cost deterministic mock transcriber, and live microphone capture testing with Google Speech-to-Text as an optional dependency.

---

## Deliverables Completed

- [x] **D1–2 (Data Contracts & Schemas):**
  - Authoritative audio contracts in `academia_audio.schemas` (`AudioChunk`, `AudioFormat`, `AudioError`, `AudioErrorCode`).
  - Strict Pydantic V2 transcript contracts in [`src/sde4_stt/schemas/transcript.py`](src/sde4_stt/schemas/transcript.py) (`TranscriptSegment`, `WordTiming`, `TranscriptError`, `TranscriptEvent`, `TranscriptEventType`).
  - Strict boundary validation, ISO/BCP-47 language tag validation, and timestamp order validation.

- [x] **D3–4 (Provider-Neutral Adapter Interface & FakeTranscriber):**
  - Abstract base adapter in [`src/sde4_stt/adapters/base.py`](src/sde4_stt/adapters/base.py) enforcing the lifecycle: `start_session` -> `process_chunk` -> `finish_session`.
  - Offline, deterministic mock transcriber in [`src/sde4_stt/adapters/fake_transcriber.py`](src/sde4_stt/adapters/fake_transcriber.py) supporting canned scripts, chunk hashing, and simulated error injection without any external APIs.

- [x] **D5–6 (Segment Accumulation & Audio Source Integration):**
  - Transcript segment accumulator in [`src/sde4_stt/accumulator.py`](src/sde4_stt/accumulator.py) tracking active sessions and assembling final ordered utterances.
  - Integration with W1 `MockMicrophone` for synthetic streaming.

- [x] **D7 (CLI Demos & Tests):**
  - Working mock demonstration in [`demo_stt.py`](demo_stt.py).
  - Working live microphone tester in [`manual_text.py`](manual_text.py) supporting both `--engine mock` and `--engine real`.

---

## Week 1 Code Review Fixes Implemented

- [x] **Google SpeechRecognition Made Strictly Optional:**
  - Removed eager `import speech_recognition` from all top-level module paths.
  - `RealSpeechTranscriber` in [`src/sde4_stt/adapters/real_transcriber.py`](src/sde4_stt/adapters/real_transcriber.py) imports `speech_recognition` lazily inside `__init__()`.
  - Raises an informative, actionable `ImportError` if initialized without the optional dependency.
- [x] **Clean `adapters/__init__.py` Export:**
  - [`src/sde4_stt/adapters/__init__.py`](src/sde4_stt/adapters/__init__.py) exports *only* `BaseTranscriberAdapter` and `FakeTranscriber`.
  - `RealSpeechTranscriber` is imported directly by consumers when optional real provider features are needed.
- [x] **Optional Dependencies Declared in `pyproject.toml`:**
  - `SpeechRecognition` and `sounddevice` are isolated under `[project.optional-dependencies]` as `google-stt`.
  - Core install (`pip install -e .`) remains ultra-lightweight with only `pydantic`.
- [x] **Single Authoritative `AudioChunk` Definition:**
  - Removed duplicate `src/sde4_stt/schemas/audio.py`.
  - Reused W1's canonical dataclass from `academia_audio.schemas` throughout the package.
- [x] **Honest Metadata & Offline Capabilities:**
  - Corrected docstrings: Google Web Speech requires an internet connection; `FakeTranscriber` is the offline implementation.
  - Fixed confidence representation: does not fabricate confidence scores (uses schema default `1.0` or `None`).

---

## Test Verification

Verified on a clean virtual environment without `SpeechRecognition`:

```text
tests/test_accumulator.py .....                                          [  2%]
tests/test_adapters.py ...................                               [ 12%]
tests/test_cli.py .....                                                  [ 14%]
tests/test_schemas.py .................................................. [ 80%]
.....                                                                    [ 82%]
tests/test_source_and_chunker.py .......................                 [ 94%]
```

- All adapter contract tests pass.
- Package imports and `FakeTranscriber` function cleanly with zero third-party packages installed.

