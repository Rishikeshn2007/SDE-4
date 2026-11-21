## W1 Day 1-7: audio schemas, mock mic, chunker, CLI, tests
- Schemas (AudioFormat/AudioChunk/AudioError) defined once in `academia_audio/schemas.py`
- Deterministic MockMicrophone + chunker (timestamps + strictly increasing sequence IDs)
- CLI: `python -m academia_audio`
- Tests: invalid, empty, corrupt, happy path, determinism, CLI

### Test output
```
...................................................................      [100%]
67 passed in 0.07s
```
No secrets, recordings or personal data committed.
