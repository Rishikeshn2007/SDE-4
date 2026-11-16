# SDE-4 – Context and Reasoning Voicebot

## Project Overview

This project develops a context-aware reasoning system that processes synthetic context information, generates grounded answers, and prepares safe workflow proposals.

The project is developed in three stages: Week 1, Week 2, and Week 3.

The system uses mock implementations and synthetic data for development and testing.

## Week 1 – Context and Reasoning Foundation

- Defined reusable context schemas.
- Created source references and context items.
- Implemented reasoning requests and results.
- Developed deterministic mock reasoning.
- Added validation and unit tests.

## Week 2 – Capture Adapter, Context Builder and LLM Adapter

- Implemented opt-in capture adapter interfaces.
- Added synthetic frame processing.
- Created bounded context selection.
- Implemented recency and relevance filtering.
- Added stale context filtering.
- Developed a mock LLM adapter.
- Added timeout, retry, and structured validation tests.

## Week 3 – Source-Linked Observations and Workflow Handoff

### Days 15–16: Observation Management

- Created timestamped observations.
- Linked observations to their original sources.
- Added stale observation filtering.
- Added duplicate observation handling.
- Implemented consent management.
- Added pending-context clearing when consent is withdrawn.

### Days 17–18: Grounded Answers

- Generated answers using available context.
- Included source IDs in reasoning results.
- Added explicit no-evidence responses.
- Prevented answers from being based on unsupported information.

### Days 19–20: Prompt Injection Protection and Workflow Handoff

- Treated captured context as untrusted data.
- Created a validated WorkflowProposal schema.
- Added workflow proposal planning.
- Implemented mock workflow handoff.
- Required explicit confirmation.
- Prevented automatic workflow execution.

### Day 21: Integration

- Integrated observations and consent management.
- Connected grounded answer generation.
- Integrated workflow proposal creation and handoff.
- Created a synthetic integration demo.

## Project Structure

```text
SDE-4/
│
├── adapters/
│   ├── capture.py
│   └── vision.py
│
├── context_builder/
│   └── builder.py
│
├── examples/
│   ├── demo.py
│   ├── synthetic_frames.py
│   └── week3_demo.py
│
├── llm/
│   └── client.py
│
├── observations/
│   ├── observation_builder.py
│   └── consent_manager.py
│
├── prompts/
│   └── prompt_v1.json
│
├── reasoning/
│   ├── mock_reasoning.py
│   └── grounded_answer.py
│
├── schemas/
│   ├── context.py
│   └── workflow.py
│
├── workflow/
│   ├── planner.py
│   └── handoff.py
│
├── tests/
│   ├── test_schemas.py
│   ├── test_reasoning.py
│   ├── test_week2.py
│   ├── test_week3_observations.py
│   ├── test_week3_grounded_answers.py
│   └── test_week3_workflow.py
│
├── README.md
└── .gitignore
```

## Technologies Used

- Python
- Dataclasses
- Unit Testing
- Mock Reasoning
- Synthetic Context Data
- Context Validation

## Running the Project

### Run the Week 3 Integration Demo

```bash
python -m examples.week3_demo
```

### Run the Complete Test Suite

```bash
python -m unittest discover -s tests -v
```

## Testing

The project has been developed with automated unit tests covering:

- Schema validation
- Reasoning functionality
- Context building
- Observation timestamps
- Stale and duplicate observation filtering
- Consent management
- Grounded answers
- Source references
- No-evidence responses
- Workflow proposal validation
- Mock workflow handoff

The latest reported test count is 60 tests.

## Safety and Privacy

- Capture remains disabled by default.
- Only synthetic data is used in the integration demo.
- Context content is treated as untrusted data.
- Answers are grounded in available context.
- Workflow proposals require confirmation.
- Workflow actions are not automatically executed.
- No external LLM provider or API key is required for the mock demo.

## Conclusion

The SDE-4 Context and Reasoning project demonstrates a modular approach to context processing, evidence-based answers, and safe workflow handoff.

The three development stages establish a foundation for a context-aware voice assistant with source-linked information and controlled workflow proposals.