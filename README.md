# SDE 4 – Workstream W2: Speech-to-Text Pipeline (Weeks 1, 2 & 3)

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
[ FallbackAdapter ]     (W3: Automatic recovery to mock on network/quota failure)
         │
         ▼
[ Provider-Neutral Adapter ] (e.g. FakeTranscriber / RealSpeechTranscriber)
         │
         ▼
[ EventDeduplicator ]   (Duplicate suppression, Interim/Revised/Final reconciliation)
         │
         ▼
[ Segment Accumulator ] (Ordered committed final segments)
         │
         ▼
[ EventBridgePublisher ] (W3: Publishes all events to W5 backend event stream)
         │
         ▼
Ordered Full Utterance / Transcript → W5 Backend SSE Stream
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

## Week 3: Revisions, Session Awareness, Fallback & Event-Stream Integration (Days 15–21)

### Day 15–16 Deliverables: Transcript Revision, Finalization & Session Awareness

**New Event Types** ([`src/sde4_stt/schemas/transcript.py`](src/sde4_stt/schemas/transcript.py)):
- `REVISED`: A non-final revision of a previously emitted interim hypothesis. Like `INTERIM`, it cannot supersede a committed `FINAL` for the same sequence number.
- `CANCELLED`: Emitted when an in-flight transcription session is cleanly cancelled (not treated as an error).

**Session Management** ([`src/sde4_stt/session.py`](src/sde4_stt/session.py)):
- `CancellationToken`: Thread-safe cancellation signal (wraps `threading.Event`).
- `SessionContext`: Per-session container holding `session_id`, `confidence_threshold`, and `CancellationToken`.
- `SessionManager`: Thread-safe registry to create, retrieve, cancel, and remove sessions by ID.

**Confidence Threshold Enforcement** (in [`src/sde4_stt/orchestrator.py`](src/sde4_stt/orchestrator.py)):
- Configurable `confidence_threshold` per orchestrator instance.
- When a committed `FINAL` segment's confidence score falls below the threshold, a recoverable `LOW_CONFIDENCE` ERROR event is emitted alongside it.
- The final segment itself is **never dropped** — consumers decide how to handle low-confidence output.

**Updated Deduplicator** ([`src/sde4_stt/dedup.py`](src/sde4_stt/dedup.py)):
- `REVISED` events update the buffered hypothesis for a sequence but are silently suppressed if a `FINAL` for that sequence is already committed.
- `CANCELLED` events are stored with lifecycle events (alongside `START`, `COMPLETE`, `ERROR`).

### Day 17–18 Deliverables: Cancellation & Automatic Mock Provider Fallback

**Cancellation** ([`src/sde4_stt/adapters/base.py`](src/sde4_stt/adapters/base.py), [`src/sde4_stt/adapters/fake_transcriber.py`](src/sde4_stt/adapters/fake_transcriber.py)):
- `cancel()` method added to `BaseTranscriberAdapter` (default no-op; subclasses override).
- `FakeTranscriber.cancel()` immediately marks the session inactive and emits a `CANCELLED` event.
- `TranscriptionOrchestrator` checks the `CancellationToken` before each chunk. If cancelled, it calls `adapter.cancel()`, emits the `CANCELLED` event, and returns early — cleanly, without raising an error.

**Automatic Mock Fallback** ([`src/sde4_stt/fallback.py`](src/sde4_stt/fallback.py)):
- `FallbackAdapter` wraps any primary adapter and an optional secondary.
- On recoverable failures (network errors, quota exhaustion, rate-limiting, provider timeouts), it:
  1. Emits a `FALLBACK_ACTIVATED` ERROR event (recoverable=True) so consumers know a switch occurred.
  2. Transparently starts the fallback provider (`FakeTranscriber` by default) with the **same session ID and metadata**.
  3. Continues processing — no data is lost, no session ID changes.
- Non-recoverable failures (bad input, programming errors) propagate as ERROR events without fallback.
- Fallback cannot loop: if the fallback itself fails, an ERROR event is emitted and no further retry/fallback occurs.

**Extended Error Codes** ([`src/sde4_stt/retry.py`](src/sde4_stt/retry.py)):
- `QUOTA_EXHAUSTED`: Maps `PermissionError` from provider.
- `RATE_LIMITED`: Explicit rate-limit classification.
- `NETWORK_ERROR`: Maps `ConnectionError` and `OSError`.

### Day 19–20 Deliverables: W1 Audio Events & W5 Backend Event-Stream Integration

**W1 Audio Integration:**
- The orchestrator natively accepts W1 `AudioChunk` objects from `academia_audio`.
- Out-of-order chunks are handled by `EventDeduplicator` (ordered by `sequence_number`).
- Missing chunks are tolerated — the pipeline continues with available audio.
- No duplicate audio schema is ever defined; the single W1 `AudioChunk` is the authority.

**W5 Backend Event-Stream Bridge** ([`src/sde4_stt/event_bridge.py`](src/sde4_stt/event_bridge.py)):
- `EventBridgePublisher`: Publishes every `TranscriptEvent` to the W5 backend event stream via a dependency-injected `publish_fn: Callable[[session_id, event_type, data_dict], None]`.
- Fully decoupled from transport — in production, pass `backend.app.events.add_event`; in tests, pass any callable (e.g. a list append).
- Publish errors from the backend are caught and stored in `publish_errors`; they never crash the STT pipeline.
- `make_no_op_publisher()` utility returns a safe no-op publisher for use as a default.

**Published event types to W5 backend:**
| Event Type | Condition |
|---|---|
| `START` | Session opens |
| `INTERIM` | Partial hypothesis emitted |
| `REVISED` | Hypothesis correction emitted |
| `FINAL` | Committed, immutable segment |
| `COMPLETE` | Session ends cleanly |
| `CANCELLED` | Session cancelled cleanly |
| `ERROR` | Provider error, LOW_CONFIDENCE flag, FALLBACK_ACTIVATED notification |

### Day 21 Deliverable: Integration Verification & Demo

Run the Week 3 end-to-end mock demonstration (no API keys, no network, fully offline):

```bash
python demo_w3.py
```

Demo output covers all 4 integration scenarios:
1. **Standard Mock Pipeline** — W1 audio → STT → W5 Backend Event Stream (START, INTERIM, FINAL, COMPLETE events published).
2. **Network Failure & Automatic Fallback** — `ConnectionError` from primary → `FALLBACK_ACTIVATED` → `FakeTranscriber` takes over seamlessly.
3. **Mid-Stream Cancellation** — Session cancelled via `SessionManager` → `CANCELLED` event emitted cleanly (not an error).
4. **Confidence Threshold Flagging** — Segments below threshold trigger `LOW_CONFIDENCE` ERROR events while keeping the transcript.

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

## Week 4: Release Hardening & Demonstration (Days 22–30)

### Day 22–24 Deliverables: Latency Benchmarking & Performance Metrics
- **Benchmarking CLI Utility** ([`benchmarks/benchmark_latency.py`](benchmarks/benchmark_latency.py)):
  - Evaluates transcription latency under controlled synthetic audio fixtures without network calls.
  - Automatically computes total iterations, min, max, mean, median (P50), P95, P99, and standard deviation.
  - Persists JSON benchmark reports to `benchmarks/results/` for reproducible release validation.
  ```bash
  python benchmarks/benchmark_latency.py --iterations 50
  ```

### Day 25–27 Deliverables: Long-Session Reliability, Cancellation & Redacted Logging
1. **Long-Session Consistency** ([`tests/test_long_session_reliability.py`](tests/test_long_session_reliability.py)):
   - Verifies monotonic sequence ordering, zero duplicate finals, zero lost segments, and interim reconciliation over 50–100+ chunks.
2. **Cancellation Consistency**:
   - Verifies clean in-flight cancellation across processing stages without task leakage or cross-session state corruption.
3. **Structured Redacted Logging** ([`src/sde4_stt/logging.py`](src/sde4_stt/logging.py), [`tests/test_redacted_logging.py`](tests/test_redacted_logging.py)):
   - Implements `RedactedFilter` and `RedactedFormatter` ensuring zero leakage of spoken transcript text, raw PCM audio bytes, or API credentials into log streams.

### Day 28–29 Deliverables: Provider Setup Guide, Known Limitations & Regression Fixtures
- Comprehensive setup guide in [`docs/PROVIDER_SETUP.md`](docs/PROVIDER_SETUP.md).
- Sample environment template in [`.env.example`](.env.example).
- Deterministic regression fixtures in [`tests/test_regression_fixtures.py`](tests/test_regression_fixtures.py).

### Day 30 Deliverable: Final Release Demonstration
Run the Week 4 complete hardening and demonstration script:
```bash
python demo_w4.py
```

---

## Known Limitations

1. **Network Dependency for Real STT:** `RealSpeechTranscriber` requires outbound HTTPS access to Google Speech endpoints. Network drops automatically trigger `FallbackAdapter` to `FakeTranscriber`.
2. **Estimated Word Timings on Web STT:** Google Web Speech API supplies plain text without word-level offsets; timings emitted in `RealSpeechTranscriber` are mathematically estimated across chunk boundaries rather than genuine phonetic alignments.
3. **Chunked Buffering on HTTP STT:** Real provider operates via discrete request buffers on session finish rather than a full-duplex streaming gRPC connection.
4. **Cancellation Bounds on Native Provider Calls:** While orchestrator loops cancel chunk processing immediately, synchronous in-flight network requests are abandoned and drained safely by thread executors.

---

## Running Live Microphone STT & Demos

```bash
# Run Week 1 STT demonstration:
python demo_stt.py

# Run Week 2 orchestration demonstration:
python demo_w2.py

# Run Week 3 end-to-end integration demonstration (100% offline):
python demo_w3.py

# Run Week 4 final release demonstration (100% offline):
python demo_w4.py

# Run latency benchmarking utility:
python benchmarks/benchmark_latency.py --iterations 50

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
# Run complete test suite (274 tests, 100% offline):
python -m pytest -v

# Run Week 4 specific suites:
python -m pytest tests/test_benchmarks.py -v
python -m pytest tests/test_redacted_logging.py -v
python -m pytest tests/test_long_session_reliability.py -v
python -m pytest tests/test_regression_fixtures.py -v
```
