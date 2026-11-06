# SDE 4 – Workstream W2: Speech-to-Text Pipeline (Weeks 1 & 2)

**Student:** Suresh V Patil  
**Team:** SDE 4  
**Workstream:** W2 – Speech-to-text  
**Project:** Academia – AI Voice Co-Pilot  

---

## Architecture & Contract Overview

The speech-to-text pipeline serves as the auditory foundation for the Academia AI Voice Co-Pilot. It consumes raw audio chunks and streams structured, validated transcription events into the system.

Later workstreams (W1 Voice Ingestion, Context Engine, Agent Orchestrator, LLM Reasoning) depend strictly on these contracts.

```
Audio Input (Mic/Stream)
         │
         ▼
[ AudioPreprocessor ]  (Resampling to 16kHz, RMS Normalization)
         │
         ▼
[ RetryableAdapter ]    (Timeouts, Exponential Backoff, Error Normalization)
         │
         ▼
[ Provider-Neutral Adapter ] (e.g. FakeTranscriber / RealSpeechTranscriber)
         │
         ▼
[ EventDeduplicator ]   (Duplicate suppression, Interim/Final reconciliation)
         │
         ▼
[ Segment Accumulator ] (Ordered committed final segments)
         │
         ▼
Ordered Full Utterance / Transcript
```

---

## Week 1 Summary: Foundation & First Vertical Slice (Days 1–7)

### Day 1–2 Deliverables: Transcript Schemas
Defined in [`src/sde4_stt/schemas/transcript.py`](src/sde4_stt/schemas/transcript.py):
- `TranscriptEventType`: START, INTERIM, FINAL, COMPLETE, ERROR
- `WordTiming`: Word-level alignment timestamps with confidence
- `TranscriptSegment`: Monotonic segment with duration, text, confidence, language, word timings
- `TranscriptError`: Structured diagnostic errors (`code`, `message`, `details`, `recoverable`)
- `TranscriptEvent`: Immutably typed event stream payload

### Day 3–4 Deliverables: Provider-Neutral Adapter & Deterministic Fake Transcriber
Defined in [`src/sde4_stt/adapters/base.py`](src/sde4_stt/adapters/base.py) & [`src/sde4_stt/adapters/fake_transcriber.py`](src/sde4_stt/adapters/fake_transcriber.py):
- `BaseTranscriberAdapter`: Abstract interface (`start_session`, `process_chunk`, `finish_session`, `transcribe_stream`)
- `FakeTranscriber`: 100% deterministic mock transcriber (zero external API keys, offline capable)

### Day 5–6 Deliverables: Ordered Segment Accumulator
Defined in [`src/sde4_stt/accumulator.py`](src/sde4_stt/accumulator.py):
- `SegmentAccumulator`: Collects and sorts `FINAL` segments by `sequence_number`, enforcing stream lifecycle

### Day 7 Deliverable: Mock Mode Demonstration
Run Week 1 demo:
```bash
python demo_stt.py
```

---

## Week 2: Orchestration, Dedup, Retries & Preprocessing (Days 8–14)

### Day 8–9 Deliverables: Transcription Orchestrator
Defined in [`src/sde4_stt/orchestrator.py`](src/sde4_stt/orchestrator.py):
- `TranscriptionOrchestrator`: End-to-end driver connecting raw/preprocessed chunks through the adapter layer to reconciled transcript outputs.
- `TranscriptionResult`: Encapsulates ordered segments, all events, elapsed duration, chunks count, and deduplication statistics.
- **Exception Boundary:** Guarantees no raw exceptions leak out of the pipeline.

### Day 10–11 Deliverables: Ordering, De-duplication & Reconciliation
Defined in [`src/sde4_stt/dedup.py`](src/sde4_stt/dedup.py):
- `EventDeduplicator`:
  - **Duplicate suppression:** Silently drops events with already-seen `event_id`s.
  - **Interim/Final reconciliation:** When a committed `FINAL` segment arrives for a sequence number, any buffered `INTERIM` hypothesis for that sequence is discarded.
  - **Ordered extraction:** Returns strictly sorted final segments and reconciled event streams.

### Day 12–13 Deliverables: Timeouts, Retries, VAD & Audio Preprocessing
1. **Resilience Layer** ([`src/sde4_stt/retry.py`](src/sde4_stt/retry.py)):
   - `RetryConfig`: Immutable configuration for `max_retries`, `timeout_s`, `backoff_base_s`, `backoff_factor`, and `per_attempt_timeout_s`.
   - `NormalizedError`: Provider-agnostic error normalization mapping raw exceptions to standard codes (`TIMEOUT`, `PROVIDER_ERROR`, `INVALID_INPUT`, `UNKNOWN_ERROR`).
   - `RetryableAdapter`: Adapter wrapper applying genuine operation timeout enforcement via managed worker execution, deadline bounds, and exponential backoff.

2. **Voice Activity Detection (VAD)** ([`src/sde4_stt/vad.py`](src/sde4_stt/vad.py)):
   - `VoiceActivityDetector`: Stateful, energy-based VAD with configurable RMS threshold, minimum speech duration, silence hangover, and adaptive noise floor estimation.

3. **Audio Preprocessor** ([`src/sde4_stt/preprocessing.py`](src/sde4_stt/preprocessing.py)):
   - `AudioPreprocessor`:
     - **Anti-Aliasing Resampling:** Applies windowed-sinc FIR low-pass filter when downsampling to suppress frequencies above Nyquist (0.45 * target_rate / source_rate), avoiding aliasing distortion.
     - **Channel Conversion:** Supports stereo-to-mono downmixing (channel averaging) and mono-to-stereo upmixing.
     - **Clipping-Free RMS Normalization:** Scales audio amplitude to uniform target RMS level while utilizing headroom scaling to prevent digital clipping.
     - **Immutable chunk transformation:** Returns new W1 `AudioChunk` instances without mutating inputs.

### Day 14 Deliverables: Contract Tests & Prerecorded Synthetic Demo
- Full contract test suites verifying end-to-end determinism, error boundaries, retries, resampling, and deduplication.
- Live synthetic fixture demonstration script: [`demo_w2.py`](demo_w2.py).

```bash
# Run Week 2 full synthetic demonstration:
python demo_w2.py
```

---

## Installation & Dependency Modes

Standard / Mock installation (default path, zero external API keys, offline capable):
```bash
pip install -e .
```

Optional Google STT & Microphone hardware installation:
```bash
pip install -e ".[google-stt]"
```

Development test suite installation:
```bash
pip install -e ".[dev]"
```

---

## Running Live Microphone STT & Demos

```bash
# Run Week 1 STT demonstration:
python demo_stt.py

# Run Week 2 orchestration demonstration:
python demo_w2.py

# List available audio input devices:
python manual_text.py --list-devices

# Mock engine with real microphone audio:
python manual_text.py --engine mock --seconds 2

# Real Google Speech Recognition with real microphone audio:
python manual_text.py --engine real --seconds 5
```

---

## Running the Complete Test Suite

```bash
# Run all 192 unit and contract tests:
python -m pytest -v

# Run specific Week 2 test suites:
python -m pytest tests/test_orchestrator.py -v
python -m pytest tests/test_dedup.py -v
python -m pytest tests/test_retry.py -v
python -m pytest tests/test_preprocessing.py -v
```
