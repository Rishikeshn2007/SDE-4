## W2 – Audio & VAD (Week 2)

Device adapter, audio lifecycle state machine, Voice Activity Detection (VAD), bounded buffer with backpressure, comprehensive tests, and mock manual testing. Stdlib only.

### Quick Start & Commands

```bash
# Activate your virtual environment
source venv/bin/activate       # Linux/macOS
# or: .\venv\Scripts\Activate.ps1   # Windows PowerShell

# Run full test suite (Week 1 + Week 2: 98 passing tests)
python -m pytest -v

# Run the standalone Week 2 manual testing script (mock mode, zero dependencies)
python manual_test_w2.py

# Run Week 1 CLI demo
python -m academia_audio
```

### Week 2 Architecture & Modules

| Module | Contents |
|---|---|
| `academia_audio/device.py` | `DeviceAdapter` interface, `MockDeviceAdapter`, `DeviceInfo`, `PermissionState` (`granted`, `denied`, `unsupported`). Handles errors gracefully without crashing. |
| `academia_audio/lifecycle.py` | `AudioPipeline`, `LifecycleState` (`stopped`, `running`, `paused`). Implements `start()`, `pause()`, `resume()`, `stop()`. Rejects illegal transitions and guarantees buffer release on stop. |
| `academia_audio/vad.py` | `BaseVAD` interface, `MockVAD`, `VADResult`, `compute_rms()`. Deterministic speech vs. non-speech classification with configurable energy threshold and minimum speech duration. Filters out transient clicks and background noise. |
| `academia_audio/buffer.py` | `BoundedAudioBuffer`, `OverflowStrategy` (`drop_oldest`, `drop_newest`, `reject`). Enforces max capacity, backpressure, dropped-chunk accounting, and resource release. |
| `manual_test_w2.py` | Standalone manual test runner validating all Week 2 requirements and edge cases in 100% mock mode. |

### Strict Acceptance Criteria Verification

- **No crashes for denied permissions or unsupported devices**: `MockDeviceAdapter` and `AudioPipeline` raise typed `AudioError` (`PERMISSION_DENIED`, `DEVICE_UNSUPPORTED`) gracefully without unhandled exceptions.
- **Illegal lifecycle transitions rejected**: `AudioPipeline` enforces the state machine (`STOPPED`, `RUNNING`, `PAUSED`). Illegal calls (e.g. `start()` while running, `pause()` while stopped) raise `AudioError(ILLEGAL_STATE_TRANSITION)`.
- **Stop releases the buffer**: Calling `pipeline.stop()` releases all chunks held in `BoundedAudioBuffer` (`buffer.size == 0`).
- **VAD configuration works and is deterministic**: `MockVAD` reliably distinguishes silence, background noise, short transient spikes, and sustained speech with identical outputs on repeated runs.
- **Buffer remains bounded**: Buffer never exceeds configured capacity.
- **Backpressure and dropped-chunk counters**: When full, `push()` applies the configured overflow strategy and increments `dropped_chunks`.
- **Edge cases tested**: Audio gaps, late/out-of-order chunks, transient spikes, and background noise are covered in unit tests and the manual test runner.
- **100% Mock Mode**: No physical microphone, network, or external API required.
