# Context and Reasoning System

## Project Overview

This project implements a context-aware reasoning system that processes synthetic context information and generates responses using a mock reasoning and LLM architecture.

The project is developed in two weeks:

- Week 1: Context schemas and mock reasoning.
- Week 2: Opt-in capture adapter, vision adapter, context builder, and LLM adapter.

## Objectives

1. Create structured context schemas.
2. Process context using mock reasoning.
3. Implement opt-in synthetic frame capture.
4. Extract text through a mock vision adapter.
5. Build bounded context using recency and relevance.
6. Implement a mock-first LLM adapter.
7. Validate generated responses.
8. Test timeout, retry, and invalid output handling.

## Project Structure

```text
w3-context-reasoning/
│
├── adapters/
│   ├── __init__.py
│   ├── capture.py
│   └── vision.py
│
├── context_builder/
│   ├── __init__.py
│   └── builder.py
│
├── llm/
│   ├── __init__.py
│   └── client.py
│
├── schemas/
│   └── context.py
│
├── reasoning/
│   └── mock_reasoning.py
│
├── prompts/
│   └── prompt_v1.json
│
├── tests/
│   ├── test_schemas.py
│   ├── test_reasoning.py
│   └── test_week2.py
│
├── examples/
│   ├── demo.py
│   └── synthetic_frames.py
│
├── README.md
└── .gitignore
```

## Week 1 Implementation

- Created reusable context schemas.
- Implemented source references and context items.
- Added request and result validation.
- Implemented deterministic mock reasoning.
- Added versioned prompts.
- Added automated unit tests.

## Week 2 Implementation

### 1. Capture Adapter
- Capture is disabled by default.
- Requires explicit opt-in.
- Uses synthetic frames only.
- Implements frame sampling.
- Enforces maximum frame size.

### 2. Vision Adapter
- Provides a mock OCR interface.
- Extracts text from synthetic frame data.
- Handles invalid text encoding.

### 3. Context Builder
- Filters stale context.
- Uses query relevance.
- Sorts context using relevance and recency.
- Enforces token budget.
- Limits the number of context items.

### 4. LLM Adapter
- Uses mock mode by default.
- Implements timeout handling.
- Supports bounded retries.
- Validates structured output.
- Rejects unknown and duplicate source IDs.
- Rejects malformed responses and certain unsafe markup.

## Privacy and Safety

- No real screenshots are captured.
- Only synthetic frames are used.
- Capture requires explicit opt-in.
- Screen capture remains disabled in the project schemas.
- Mock LLM mode requires no API key.
- Generated output is checked before acceptance.

## Running the Project

Run the complete demonstration:

```bash
python examples/demo.py
```

Run all automated tests:

```bash
python -m unittest discover -s tests -v
```

Run Week 2 tests:

```bash
python -m unittest tests.test_week2 -v
```

## Testing Results

| Test Category | Passed |
|---|---:|
| Week 1 | 16 |
| Week 2 | 15 |
| Total | 31 |

**Overall Result: 31 tests passed successfully.**

The Week 1 and Week 2 demonstrations also completed successfully.

## Conclusion

The project successfully implements a context and reasoning system with structured schemas, synthetic capture, mock vision processing, bounded context selection, and a mock-first LLM adapter.

The implementation includes timeout handling, retry support, structured output validation, and automated testing.