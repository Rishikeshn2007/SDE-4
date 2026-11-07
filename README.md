# Academia AI Voice Bot - Audio & VAD Pipeline

Foundation audio contracts, deterministic mock sources, device adapter, lifecycle state machine, Voice Activity Detection (VAD), and bounded buffering for the Academia AI Voice Bot.

Built strictly with Python standard library components for maximum reliability and portability.

---

## Quick Start

```bash
# 1. Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# 2. Run all unit tests (98 passed)
python -m pytest -v

# 3. Run Week 2 standalone manual test script (mock mode)
python manual_test_w2.py

# 4. Run audio stream CLI demo (Week 1)
python -m academia_audio
```

---

## Documentation by Week

- [Week 1 Audio Foundation](README_W1_SECTION.md): Audio schemas (`AudioFormat`, `AudioChunk`, `AudioError`), deterministic `MockMicrophone`, chunker, and CLI demo.
- [Week 2 Audio & VAD Pipeline](README_W2_SECTION.md): Device adapter (`DeviceAdapter`, `MockDeviceAdapter`), lifecycle controller (`AudioPipeline`), Voice Activity Detection (`MockVAD`), bounded buffer (`BoundedAudioBuffer`), and mock test runner (`manual_test_w2.py`).

---

## Core Architecture

```
academia_audio/
├── schemas.py       # Single source of truth: AudioFormat, AudioChunk, AudioError
├── chunker.py       # Deterministic chunking: raw PCM -> AudioChunk
├── mock_source.py   # Deterministic fake microphone generator
├── device.py        # DeviceAdapter, MockDeviceAdapter, DeviceInfo, PermissionState
├── buffer.py        # BoundedAudioBuffer, OverflowStrategy, dropped-chunk tracking
├── vad.py           # BaseVAD, MockVAD, VADResult, compute_rms
├── lifecycle.py     # AudioPipeline, LifecycleState state machine
├── cli.py           # CLI demonstration tool
├── __init__.py      # Unified public interface
└── __main__.py      # Package entrypoint (python -m academia_audio)
```
