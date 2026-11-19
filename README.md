# SDE-4 - Workflow Automation System

## Project Overview

This project implements a workflow automation engine with checkpointing, recovery, approval handling, audit logging, and audio/transcription support.

## Workflow Engine Features

- Workflow checkpoint creation and storage
- Resume execution from saved checkpoints
- Recovery after workflow pauses or failures
- Completed steps are skipped during resume
- Idempotency keys for workflow steps
- Step-level audit event recording
- Persistent audit logs
- Workflow progress event callbacks
- Approval request and approval ID validation
- Duplicate approval detection
- Expired approval handling
- Plan signature validation

## Audio and Speech-to-Text Integration

### Audio package (`academia_audio/`)

- Audio buffer management
- Audio chunking
- Mock audio source
- Audio device handling
- Voice activity detection
- Audio session lifecycle management
- Audio schemas and CLI support

### Speech-to-Text package (`src/sde4_stt/`)

- Transcript accumulation
- Duplicate transcript detection
- Transcript preprocessing
- Transcription orchestration
- Retry handling
- Fake and real transcriber adapters
- Transcript schemas

## Dependencies

Core dependencies:

```powershell
py -m pip install -r requirements.txt
```

Optional real speech recognition dependency:

```powershell
py -m pip install -r requirements-optional.txt
```

The real speech recognition adapter may require an internet connection. Mock-mode tests do not require a real microphone.

## Run Tests

```powershell
$env:PYTHONPATH = "$PWD\src"
py -m pytest tests -v
```

## Run Demo

```powershell
py demo.py
```

## Technologies

- Python
- Pydantic
- Pytest
- unittest
- SpeechRecognition (optional)
- JSON-based checkpoint and audit storage
- ThreadPoolExecutor

## Current Integration Status

The workflow engine, audio package, and speech-to-text package have been added to the repository and their unit tests have been verified.

Full frontend-to-backend audio upload, live transcription, approval API integration, and end-to-end testing remain separate integration tasks.
