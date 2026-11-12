# W4 Agentic Workflow

## Project Overview
A Python-based agentic workflow demonstrating safe planning, validation, approval, and execution of mock tools.

## Week 2 Features
- Workflow plan and step definitions
- Workflow state management
- Dependency validation and cycle detection
- Allow-listed tool registry
- Required and unexpected argument validation
- Permission scope validation
- Human approval for consequential steps
- Rejected and expired approval handling
- Audit event recording
- Per-step timeouts
- Bounded retries for idempotent tools
- Cancellation before the next step
- Mock-only execution

## Technologies
- Python
- Pytest
- ThreadPoolExecutor
- unittest

## Run Demo
py demo.py

## Run Tests
py -m pytest tests -v

## Demo Scenarios
1. Missing approval: workflow waits for approval.
2. Approved execution: workflow succeeds.
3. Rejected execution: tool does not run.

## Safety
Only mock tools are used. Consequential steps require explicit approval. Timeouts do not forcibly terminate running Python threads, and cancellation is checked before each step.
