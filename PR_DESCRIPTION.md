## SDE 4: Week 2 – Speech-to-Text Orchestration, Ordering & De-duplication, Retries & Preprocessing (W2)

**Student:** Suresh V Patil  
**Team:** SDE 4  
**Workstream:** W2 – Speech-to-text (Days 8–14)  
**Project Folder:** `projects/sde-4-voicebot/` | **Branch:** `team/sde-4-voicebot` (working on `suresh`)  

---

### Deliverables Completed

- [x] **D8–9 (Transcription Orchestrator):** Implemented `TranscriptionOrchestrator` and `TranscriptionResult` in [`src/sde4_stt/orchestrator.py`](src/sde4_stt/orchestrator.py) to manage the entire chunk-to-transcript pipeline end-to-end.
- [x] **D10–11 (Ordering, De-duplication & Reconciliation):** Built `EventDeduplicator` in [`src/sde4_stt/dedup.py`](src/sde4_stt/dedup.py) with duplicate event ID suppression, interim-final reconciliation, and strictly sorted final segments.
- [x] **D12–13 (Timeouts, Bounded Retries & Error Normalization):** Built `RetryConfig`, `NormalizedError`, and `RetryableAdapter` in [`src/sde4_stt/retry.py`](src/sde4_stt/retry.py) with exponential backoff and cumulative timeouts. Guarantees no raw exceptions leak out.
- [x] **D12–13 (Audio Preprocessing & VAD):** Implemented `AudioPreprocessor` in [`src/sde4_stt/preprocessing.py`](src/sde4_stt/preprocessing.py) providing anti-aliased sinc-FIR downsampling, channel conversion (mono <-> stereo), and clipping-free RMS normalization. Implemented reusable stateful `VoiceActivityDetector` in [`src/sde4_stt/vad.py`](src/sde4_stt/vad.py).
- [x] **D14 (Contract Tests & Demo):** Comprehensive contract test suite in [`tests/test_orchestrator.py`](tests/test_orchestrator.py), [`tests/test_dedup.py`](tests/test_dedup.py), [`tests/test_retry.py`](tests/test_retry.py), [`tests/test_preprocessing.py`](tests/test_preprocessing.py), and [`tests/test_vad.py`](tests/test_vad.py). Runnable synthetic demo in [`demo_w2.py`](demo_w2.py).

---

### Week 1 Code Review Feedback Fixes

- [x] **Google SpeechRecognition Optional:** Removed eager `import speech_recognition` from all top-level package paths. `RealSpeechTranscriber` uses lazy import inside `__init__`, raising a descriptive error instructing how to install `.[google-stt]`.
- [x] **Clean Adapters Export:** `sde4_stt/adapters/__init__.py` strictly exports only `BaseTranscriberAdapter` and `FakeTranscriber`. `RealSpeechTranscriber` is imported directly by consumers when needed.
- [x] **pyproject.toml Optional Extra:** Declared `google-stt = ["SpeechRecognition>=3.10.0", "sounddevice>=0.4.0"]` under `[project.optional-dependencies]` with standard dependencies remaining lightweight.
- [x] **Single Authoritative AudioChunk Schema:** Deleted duplicate Pydantic `AudioChunk` in `sde4_stt/schemas/audio.py`. Reused canonical W1 dataclass from `academia_audio.schemas`.
- [x] **Restored Live Microphone & Demos:** Updated `manual_text.py` and `demo_stt.py` to use W1 `AudioChunk` and `AudioFormat`. Verified live recording with `--engine mock --seconds 2` and `--engine real --seconds 3`.
- [x] **Reusable VAD & Real STT Orchestrator Integration:** Wired `VoiceActivityDetector` and `TranscriptionOrchestrator` into `manual_text.py`.

---

### Test Suite Output

```
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.6.0
rootdir: C:\Users\sures\Desktop\SDE-4
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, flask-1.3.0
collected 192 items

tests/test_accumulator.py .....                                          [  2%]
tests/test_adapters.py ............                                      [  8%]
tests/test_cli.py .....                                                  [ 11%]
tests/test_dedup.py ...........                                          [ 17%]
tests/test_orchestrator.py .....................                         [ 28%]
tests/test_preprocessing.py ........................                     [ 40%]
tests/test_retry.py .........................                            [ 53%]
tests/test_schemas.py .................................................. [ 79%]
.....                                                                    [ 82%]
tests/test_source_and_chunker.py .......................                 [ 94%]
tests/test_vad.py ...........                                            [100%]

======================= 192 passed, 2 warnings in 1.40s =======================
```

---

### Acceptance Criteria Verification

- [x] **Chunk to transcript events works end to end in mock mode:** Verified via `TranscriptionOrchestrator` and `demo_w2.py`.
- [x] **Out-of-order and duplicate segments are handled correctly; interim results reconcile into final ones:** Verified by 10 tests in `test_dedup.py`.
- [x] **Timeouts and bounded retries work; provider errors are normalized (no raw exceptions leak):** Verified by 16 tests in `test_retry.py` and orchestrator error boundary tests.
- [x] **Resampling and normalization are tested:** Verified by 16 tests in `test_preprocessing.py` (downsampling, upsampling, silence handling, gain scaling).
- [x] **Contract tests cover the adapter and events; the default path needs no real provider or API key:** Verified in `test_orchestrator.py` with 100% offline deterministic execution.
- [x] **No duplicate schema definitions:** Reuses W1 `AudioChunk` and `AudioFormat` from `academia_audio.schemas` without redefining them.
- [x] **No recordings or secrets committed:** Checked via `git status` / `git ls-files`.
