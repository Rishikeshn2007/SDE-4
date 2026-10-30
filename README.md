# W3 – Context & Reasoning

## 1. Project Overview

This project demonstrates a context and reasoning system implemented in Python.

It uses structured context schemas, deterministic mock reasoning, source references,
versioned prompts, synthetic context data, and automated unit tests.

The system generates responses using supplied context rather than inventing
unsupported information.

## 2. Project Objectives

- Define schemas for context and reasoning requests and results.
- Document field types, units, and constraints.
- Validate input data and reasoning outputs.
- Use synthetic context data for demonstrations.
- Keep screen capture disabled for privacy.
- Implement deterministic mock reasoning.
- Separate trusted prompt instructions from untrusted context.
- Test valid, invalid, and edge-case inputs.

## 3. Project Structure

```text
w3-context-reasoning/
├── schemas/
│   ├── __init__.py
│   └── context.py
├── reasoning/
│   ├── __init__.py
│   └── mock_reasoning.py
├── prompts/
│   └── prompt_v1.json
├── tests/
│   ├── __init__.py
│   ├── test_schemas.py
│   └── test_reasoning.py
├── examples/
│   ├── demo.py
│   └── synthetic_frames.py
├── README.md
└── .gitignore