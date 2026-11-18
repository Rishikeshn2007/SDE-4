# W4 Agentic Workflow

## Project Overview

A Python-based agentic workflow demonstrating safe planning, validation, approval, execution, checkpoint recovery, and audit tracking using mock tools.

## Week 2 Features

- Workflow plan and step definitions
- Workflow state management
- Dependency validation and cycle detection
- Allow-listed tool registry
- Required and unexpected argument validation
- Permission scope validation
- Human approval for consequential steps
- Rejected and expired approval handling
- Per-step timeouts
- Bounded retries for idempotent tools
- Cancellation before the next step
- Mock-only execution

## Week 3 Features

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

## Technologies

- Python
- Pytest
- ThreadPoolExecutor
- unittest
- JSON-based checkpoint and audit storage

## Run Demo

```powershell
py demo.py