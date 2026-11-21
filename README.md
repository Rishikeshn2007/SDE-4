# Academia AI Voice Bot - Audio & VAD Pipeline

Foundation audio contracts, deterministic mock sources, device adapter, lifecycle state machine, Voice Activity Detection (VAD), bounded buffering, speech event streaming, device-loss recovery, session cancellation, and speech-to-text integration for the Academia AI Voice Bot.

Built strictly with Python standard library components for maximum reliability and portability.

---

## Quick Start

```bash
# 1. Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# 2. Run all unit & integration tests (112 passed)
python -m pytest -v

# 3. Run Week 3 standalone manual test script (mock mode)
python scripts/manual_week3_test.py
# or:
python manual_test_w3.py

# 4. Run Week 3 CLI demo
python -m academia_audio --demo3
```

---

## Documentation by Week

- [Week 1 Audio Foundation](README_W1_SECTION.md): Audio schemas (`AudioFormat`, `AudioChunk`, `AudioError`), deterministic `MockMicrophone`, chunker, and CLI demo.
- [Week 2 Audio & VAD Pipeline](README_W2_SECTION.md): Device adapter (`DeviceAdapter`, `MockDeviceAdapter`), lifecycle controller (`AudioPipeline`), Voice Activity Detection (`MockVAD`), bounded buffer (`BoundedAudioBuffer`), and mock test runner (`manual_test_w2.py`).
- [Week 3 Speech Events & Transcription](README_W3_SECTION.md): Speech events (`SpeechStartEvent`, `SpeechEndEvent`, `AudioChunkEvent`), device-loss recovery, session cancellation, audio normalization, transcription bridge, and mock test runner (`scripts/manual_week3_test.py`).

---

## Core Architecture

```
academia_audio/
├── schemas.py         # Audio contracts & Week 3 event schemas (single source of truth)
├── chunker.py         # Deterministic chunking: raw PCM -> AudioChunk
├── mock_source.py     # Deterministic fake microphone generator
├── device.py          # DeviceAdapter, MockDeviceAdapter, DeviceInfo, PermissionState, device disconnect/reconnect
├── buffer.py          # BoundedAudioBuffer, OverflowStrategy, dropped-chunk tracking
├── vad.py             # BaseVAD, MockVAD, VADResult, compute_rms
├── lifecycle.py       # AudioPipeline, LifecycleState (start, pause, resume, stop, cancel, device recovery)
├── normalization.py   # Audio PCM normalization & peak scaling
├── transcription.py   # Speech-to-Text integration: TranscriptionBridge, MockTranscriptionAdapter
├── cli.py             # CLI demonstration tool (--demo, --demo3)
├── __init__.py        # Unified public interface
└── __main__.py        # Package entrypoint (python -m academia_audio)

scripts/
└── manual_week3_test.py # Standalone manual test script (100% mock mode)
```
