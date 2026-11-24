# STT Provider Setup & Release Hardening Guide

**Project:** Academia AI Voice Co-Pilot  
**Workstream:** W2/W4 Speech-to-Text (STT)  
**Target Environment:** Python >= 3.10  

---

## 1. Installation Instructions

### Standard Installation (Default / Mock Provider)
The default installation runs 100% offline, requires zero external API keys or cloud accounts, and supports full synthetic testing, benchmarking, and demonstrations:

```bash
# Clone the repository
git clone https://github.com/Rishikeshn2007/SDE-4.git
cd SDE-4

# Create and activate a clean virtual environment
python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install core packages in editable mode
pip install -e .
```

### Development & Testing Dependencies
To run the automated test suite, benchmarks, and coverage checks:

```bash
pip install -e ".[dev]"
```

### Optional Real Google STT & Microphone Hardware Dependencies
If evaluating with live physical microphone input and Google Speech Recognition:

```bash
pip install -e ".[google-stt]"
```

---

## 2. Required Dependencies

Defined in `pyproject.toml`:
* **Core Runtime:** `pydantic>=2.0.0`
* **Development/Testing:** `pytest>=8.0.0`
* **Optional Google STT:** `SpeechRecognition>=3.10.0`, `sounddevice>=0.4.0`

---

## 3. Supported Environment Variables

Copy the provided `.env.example` file to configure your local runtime:

```bash
cp .env.example .env
```

| Variable Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `STT_PROVIDER` | string | `mock` | Selected STT adapter: `mock` (deterministic FakeTranscriber) or `real` (RealSpeechTranscriber). |
| `STT_LANGUAGE` | string | `en` | BCP-47 language tag (e.g. `en-US`, `en-IN`, `en`). |
| `STT_SAMPLE_RATE` | int | `16000` | Target audio sample rate in Hz (canonical rate: 16000). |
| `STT_CONFIDENCE_THRESHOLD` | float | `0.80` | Minimum confidence score [0.0–1.0]; segments below this trigger a `LOW_CONFIDENCE` error event. |
| `STT_RETRY_MAX` | int | `3` | Maximum number of retry attempts on recoverable errors. |
| `STT_RETRY_TIMEOUT_S` | float | `10.0` | Maximum overall deadline in seconds for retryable operations. |
| `GOOGLE_APPLICATION_CREDENTIALS` | string | *unset* | Path to service account credentials JSON (optional; only needed for paid Cloud STT). |

*Security Notice: Never commit actual API keys or credentials to version control. All credentials must be passed via environment variables or secret managers.*

---

## 4. Mock Provider Configuration

The mock provider (`FakeTranscriber`) is the default and recommended engine for CI/CD and offline development:
- **Zero API keys required.**
- **Deterministic output:** Identical audio chunk sequences produce identical transcript events.
- **Configurable modes:**
  1. `canned_transcript`: Unrolls an explicit sentence across chunks with simulated interim and revised events.
  2. Hash-derived vocabulary: Generates deterministic vocabulary tokens derived from SHA-256 chunk hashes.
  3. Failure simulation: Supports `fail_at_chunk_index` to test retry and fallback handling deterministically.

```python
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.orchestrator import TranscriptionOrchestrator

adapter = FakeTranscriber(canned_transcript="academia voice co-pilot is listening")
orch = TranscriptionOrchestrator(adapter=adapter)
result = orch.transcribe(audio_chunks, session_id="session_01")
print(result.full_text)
```

---

## 5. Real Provider Configuration

The real provider (`RealSpeechTranscriber`) wraps the Google Web Speech API:
- Requires network connectivity to Google speech endpoints.
- Audio chunks are aggregated and submitted via HTTP POST.
- Supports configurable timeouts, retry backoff, and automatic fallback to `FakeTranscriber` via `FallbackAdapter`.

```python
from sde4_stt.adapters.real_transcriber import RealSpeechTranscriber
from sde4_stt.fallback import FallbackAdapter
from sde4_stt.orchestrator import TranscriptionOrchestrator

# Wrap in FallbackAdapter to automatically recover if network or quota limits fail:
real_adapter = RealSpeechTranscriber(language="en-US")
resilient_adapter = FallbackAdapter(primary=real_adapter)

orch = TranscriptionOrchestrator(adapter=resilient_adapter)
result = orch.transcribe(audio_chunks, session_id="session_real")
```

---

## 6. Microphone & Audio Hardware Requirements

- **Supported Formats:** 16-bit signed PCM (little-endian, `pcm_s16le`).
- **Channels:** Mono (1 channel) or Stereo (2 channels). Stereos are automatically downmixed to mono by `AudioPreprocessor`.
- **Sample Rates:** 8000Hz, 16000Hz, 22050Hz, 24000Hz, 32000Hz, 44100Hz, 48000Hz.
  *Resampling is automatically performed using windowed-sinc anti-aliasing to 16,000 Hz.*
- **Microphone Testing Command:**
```bash
python manual_text.py --list-devices
python manual_text.py --engine mock --seconds 3
```

---

## 7. Network Requirements

| Provider | Internet Access Required? | Outbound Ports | Firewall Considerations |
| :--- | :--- | :--- | :--- |
| **Mock (`FakeTranscriber`)** | **No** (100% offline) | None | Zero network traffic |
| **Real (`RealSpeechTranscriber`)** | Yes | HTTPS (TCP 443) | Outbound access to `speech.googleapis.com` |

---

## 8. Latency Benchmark Execution

A reproducible benchmarking utility is provided in `benchmarks/`:

```bash
# Run default mock provider benchmark (50 iterations, synthetic audio fixture):
python benchmarks/benchmark_latency.py --iterations 50

# Custom duration and chunk size:
python benchmarks/benchmark_latency.py --iterations 20 --duration 3.0 --chunk-ms 100

# Benchmark without audio preprocessing:
python benchmarks/benchmark_latency.py --iterations 20 --no-preprocess
```

Results are printed in a summary table and stored in JSON format in `benchmarks/results/`.

---

## 9. Test Suite Execution

Run the complete offline test suite:

```bash
# Run all tests:
python -m pytest -v

# Run long-session consistency and cancellation tests:
python -m pytest tests/test_long_session_reliability.py -v

# Run security and redacted logging tests:
python -m pytest tests/test_redacted_logging.py -v

# Run regression fixtures:
python -m pytest tests/test_regression_fixtures.py -v

# Run latency benchmark unit tests:
python -m pytest tests/test_benchmarks.py -v
```

---

## 10. Troubleshooting

| Symptom | Probable Cause | Recommended Resolution |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'workflow'` | Root repository not in Python path | Run scripts from repository root or use `python -m pytest`. |
| `ModuleNotFoundError: No module named 'speech_recognition'` | Optional Google STT dependencies not installed | Install extra dependencies: `pip install -e '.[google-stt]'`. |
| `FALLBACK_ACTIVATED` error event in stream | Primary provider failed (network/quota) | Expected behavior; `FallbackAdapter` seamlessly switched to mock provider without losing session context. |
| `LOW_CONFIDENCE` error event emitted | Final segment confidence < `confidence_threshold` | Expected behavior; segment is preserved while notifying downstream consumers to review or prompt user. |
| Sound device permission error on Linux/macOS | Missing portaudio or microphone permissions | Install `libportaudio2` (`apt-get install portaudio19-dev`). |

---

## 11. Known Limitations

The following genuine technical limitations exist in the current implementation:

1. **Network Dependency for Real STT:**
   `RealSpeechTranscriber` depends on outbound network reachability to Google STT endpoints. Disconnections or DNS timeouts will trigger automatic fallback to `FakeTranscriber` when wrapped in `FallbackAdapter`.
2. **Estimated Word Timings:**
   The public Google Web Speech API returns only plain transcribed text, without word-level timestamp metadata. Word alignments generated by `RealSpeechTranscriber` are uniform mathematical estimates across the chunk duration, not real phonetic alignments.
3. **Chunked Buffering Characteristics:**
   `RealSpeechTranscriber` buffers audio chunks and submits them as a discrete HTTP request upon session finalization. It does not maintain a persistent gRPC bidirectional audio stream.
4. **Cancellation Bounds on External Calls:**
   While `TranscriptionOrchestrator` stops processing chunks immediately when a `CancellationToken` is cancelled, in-flight synchronous HTTP network requests made to Google STT cannot be abruptly terminated across OS threads without thread interruption; they are abandoned and drained safely by worker pools.
5. **Acoustic Environment Sensitivity:**
   Energy-based Voice Activity Detection (VAD) is calibrated for typical desktop speech levels. High ambient background noise or heavy clipping can cause false speech-start triggers.
