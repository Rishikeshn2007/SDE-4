## W3 – Audio & VAD (Week 3)

Speech Events, Device-Loss Recovery, Session Cancellation, and Speech-to-Text Transcription Integration.

### Quick Start & Commands

```bash
# Activate your virtual environment
source venv/bin/activate            # Linux/macOS
# or: .\venv\Scripts\Activate.ps1    # Windows PowerShell

# Run full test suite (Week 1 + Week 2 + Week 3: 112 passing tests)
python -m pytest -v

# Run Week 3 integration tests only
python -m pytest tests/test_week3_integration.py -v

# Run the standalone Week 3 manual testing script (mock mode, zero hardware, stdlib only)
python scripts/manual_week3_test.py
# or convenience runner:
python manual_test_w3.py

# Run Week 3 CLI demo
python -m academia_audio --demo3
```

### Week 3 Architecture & Modules

| Module | Contents |
|---|---|
| `academia_audio/schemas.py` | Week 3 event schemas: `BaseAudioEvent`, `SpeechStartEvent`, `SpeechEndEvent`, `AudioChunkEvent`, `DeviceDisconnectedEvent`, `DeviceReconnectedEvent`, `SessionCancelledEvent`. Validates `session_id`, `correlation_id`, timestamps, durations, and strictly increasing monotonic sequence IDs. |
| `academia_audio/normalization.py` | `normalize_audio_chunk()`, `normalize_pcm_bytes()`, `compute_peak_amplitude()`. Deterministic 16-bit PCM peak amplitude normalization preserving format and CRC-32 integrity. |
| `academia_audio/device.py` | Enhanced `DeviceAdapter` and `MockDeviceAdapter` with `is_connected`, `disconnect()`, `simulate_disconnect()`, and `reconnect()` for safe device-loss simulation and hardware recovery without crashing. |
| `academia_audio/lifecycle.py` | Enhanced `AudioPipeline` with: (1) strictly ordered speech event emission (`SPEECH_START` -> `AUDIO_CHUNK` -> `SPEECH_END`), (2) session & correlation ID propagation, (3) graceful device-loss detection & automatic or manual reconnection recovery, (4) cancellation stopping capture and releasing buffer (`cancel()`), and (5) event listeners & transcription sink dispatching. |
| `academia_audio/transcription.py` | Speech-to-Text integration: `TranscriptionBridge`, `MockTranscriptionAdapter` (clearly identified mock adapter conforming to team's `BaseTranscriberAdapter` contract), `MockTranscriptEvent`, `MockTranscriptSegment`. Auto-detects real `sde4_stt` if installed; falls back to mock adapter without pretending real integration is complete. |
| `scripts/manual_week3_test.py` | Standalone manual test runner verifying all Week 3 requirements in 100% mock mode with structured PASS/FAIL reporting. |

### Strict Acceptance Criteria Checklist

- [x] **Speech-start and speech-end events emitted in correct order**: `SpeechStartEvent` is guaranteed to precede any speech-bearing chunks; `SpeechEndEvent` is guaranteed to conclude the utterance upon speech cessation.
- [x] **Every event contains session and correlation IDs**: Strictly validated non-empty string IDs are propagated across all emitted events.
- [x] **Device loss mid-session detected and recovered without crashing**: Hardware disconnections are trapped via `AudioErrorCode.DEVICE_LOST`, transitioned to `LifecycleState.RECOVERING`, and re-established cleanly without crashing.
- [x] **Cancellation stops capture and releases buffer**: Calling `pipeline.cancel()` stops capture immediately, releases all buffer memory (`buffer.size == 0`), and transitions to `CANCELLED`.
- [x] **Audio events reach transcription end-to-end in mock mode**: `TranscriptionBridge` feeds speech audio chunks into the transcriber adapter, producing `START`, `INTERIM`, `FINAL`, and `COMPLETE` transcript events.
- [x] **Integration tests cover ordering, gaps, silence, and false triggers without a real mic**: Covered in `tests/test_week3_integration.py` and `scripts/manual_week3_test.py`.
- [x] **Reuse existing schemas; no duplicate definitions**: All schemas build upon and reuse `AudioFormat`, `AudioChunk`, and `AudioError` from `academia_audio/schemas.py`.
- [x] **No recordings, credentials, or secrets committed**: Zero binary audio files, credentials, or paid API keys.
