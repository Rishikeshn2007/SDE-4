## W1 – Audio & VAD (Week 1)

Audio schemas, deterministic mock microphone, chunker, CLI demo, tests. Stdlib only.

```bash
source venv/bin/activate          # your existing virtual env
pip install -r requirements-dev.txt
python -m academia_audio          # demo (one command)
python -m academia_audio --duration 1 --realtime   # live-paced demo
python -m pytest -v               # tests
```

| Module | Contents |
|---|---|
| `academia_audio/schemas.py` | `AudioFormat`, `AudioChunk`, `AudioError` (defined once) |
| `academia_audio/chunker.py` | `chunk_pcm()` deterministic PCM -> chunks |
| `academia_audio/mock_source.py` | `MockMicrophone` |
| `academia_audio/cli.py` | CLI demo |

Contract: 16-bit PCM (`pcm_s16le`); rates 8000/16000/22050/24000/32000/44100/48000 Hz; 1 or 2 channels;
`timestamp_s` = seconds from stream start; `sequence_id` starts at 0, strictly increasing; `checksum` = CRC-32.
