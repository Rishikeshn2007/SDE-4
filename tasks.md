# Rishikesh N

Overview
Foundation of the Academia AI Voice Bot audio pipeline: typed audio schemas with validation, a deterministic mock microphone source, a CLI demo, and unit tests covering bad input. Later weeks (VAD, buffering, integration with W2) depend on these contracts, so keep them clean, documented and stable. Define each schema once inside the team project folder; do not duplicate definitions across modules.

Day-wise Implementation Plan
Define audio schemas
Define AudioChunk, AudioFormat and AudioError schemas.
Implement sample-rate and channel validation, raising AudioError with clear messages.
Document each field (type, units, constraints).

Implement mock audio source
Create a fake microphone source that emits AudioChunks.
Implement a deterministic audio chunker (same input → identical chunks every run).
Include timestamps and monotonically increasing sequence IDs on every chunk.

CLI demonstration and unit testing
Build a CLI demo that streams the mock source and prints chunk metadata (sequence ID, timestamp, format, size).
Write unit tests for invalid, empty and corrupt chunks, plus the valid happy path.


Deliverables
Schema module: AudioChunk, AudioFormat, AudioError with validation
Fake microphone source and deterministic chunker (timestamps + sequence numbers)
CLI demo
Unit test suite with passing output (invalid, empty, corrupt chunks)
GitHub PR with test output in the description
Live demo of the mock audio stream (Day 7)

Acceptance Criteria
All three schemas exist, are defined once, and are documented
Invalid sample rate / channel count is rejected with AudioError
Mock source output is deterministic (two runs on same input give identical chunks)
Every chunk has a timestamp and a strictly increasing sequence ID
CLI runs with a single documented command and shows the stream
Tests cover invalid, empty and corrupt chunks; all pass
Work is on a feature branch; no direct pushes to main
PR is reviewed, includes test output, and no secrets/recordings/personal data are committed
Day 7 demo completed

# Suresh V Patil

Overview

Foundation of the speech-to-text pipeline: transcript schemas, a provider-neutral adapter, a deterministic fake transcriber and an ordered segment accumulator, all runnable in mock mode with no paid API keys. Later weeks (orchestration, de-duplication, W1 integration) depend on these contracts, so keep them clean, documented and stable. Define each schema once inside the team project folder.

Day-wise Implementation Plan

Day 1–2: Define transcript schemas
Define TranscriptSegment and TranscriptEvent schemas (timestamps, confidence, interim/final, language, errors).
Document each field (type, units, constraints) and reject invalid payloads clearly.

Day 3–4: Adapter and fake transcriber
Build a provider-neutral adapter interface.
Implement a deterministic fake transcriber (same input → identical transcript events).

Day 5–6: Segment accumulator and tests
Build an ordered segment accumulator with fixtures.
Write unit tests covering ordering, interim/final handling and invalid input.

Deliverables
TranscriptSegment and TranscriptEvent schemas with validation
Provider-neutral adapter and deterministic fake transcriber
Ordered segment accumulator with fixtures
Unit test suite with passing output
GitHub PR with test output in the description
Live demo: chunk-to-transcript in mock mode (Day 7)

Acceptance Criteria
Both schemas exist, are defined once, and are documented (timestamps, confidence, interim/final, language, errors)
Invalid payloads are rejected with clear errors
Fake transcriber is deterministic (identical output on repeated runs)
Adapter is provider-neutral; no real provider or API key is required
Accumulator returns segments in order, with fixtures covering normal and edge cases
Tests pass and cover normal, boundary and failure behaviour
Work is on a feature branch; no direct pushes to main
PR is reviewed, includes test output, and no secrets/recordings/personal data are committed
Day 7 demo completed

# Bhagya M S

Overview

Foundation of the context and reasoning layer: typed context and reasoning schemas, synthetic frames with screen capture disabled by default, deterministic mock reasoning and versioned prompts that separate trusted instructions from untrusted content. Everything runs in mock mode with no paid API keys. Define each schema once inside the team project folder.

Day-wise Implementation Plan

Day 1–2: Define schemas
Define ScreenContext, ContextItem, SourceReference and ReasoningRequest / ReasoningResult schemas.
Document each field (type, units, constraints).

Day 3–4: Synthetic frames, mock reasoning, prompts
Create synthetic frames (capture disabled by default).
Implement deterministic mock reasoning.
Add versioned prompts separating trusted instructions from untrusted content.

Day 5–6: Validation and unit tests
Implement validation of requests and results.
Write unit tests for valid, invalid and edge-case inputs.

Day 7: Pull request and demonstration
Open a GitHub pull request with test output.
Demonstrate a request producing a mock grounded response.

Deliverables
ScreenContext, ContextItem, SourceReference, ReasoningRequest/ReasoningResult schemas
Synthetic frames with capture disabled by default
Deterministic mock reasoning
Versioned prompts (trusted vs untrusted content separated)
Validation and unit tests with passing output

Acceptance Criteria
All schemas exist, are defined once, and are documented
Screen capture is off by default; only synthetic frames are used (no real screenshots or personal data)
Mock reasoning is deterministic and returns schema-validated output
Prompts are versioned and keep trusted instructions separate from untrusted content
Invalid requests/results are rejected clearly; tests pass
Work is on a feature branch; no direct pushes to main
PR is reviewed, includes test output, and no secrets/recordings/personal data are committed
Day 7 demo completed

# Renuka K N

Overview
Foundation of the agentic workflow engine: typed workflow schemas, a state machine, two harmless mock tools and an executor in which consequential actions default to awaiting approval. Everything runs in mock mode. Define each schema once inside the team project folder.

Day-wise Implementation Plan

Day 1–2: Define schemas and state machine
Define WorkflowPlan, WorkflowStep, ToolSpec, ApprovalRequest and WorkflowResult schemas.
Implement the state machine (draft, awaiting_approval, running, paused, succeeded, failed, cancelled).

Day 3–4: Mock tools and executor
Implement two harmless mock tools.
Build an executor; consequential actions default to awaiting approval.

Day 5–6: Tests
Write tests for invalid plans and state transitions.

Deliverables
Workflow schemas (WorkflowPlan, WorkflowStep, ToolSpec, ApprovalRequest, WorkflowResult)
State machine with documented transitions
Two harmless mock tools and an executor
Tests for invalid plans and state transitions with passing output

Acceptance Criteria
All schemas exist, are defined once, and are documented
State machine rejects illegal transitions
Only the two harmless mock tools exist; no unrestricted computer control or external sending
Consequential actions default to awaiting approval and never run unapproved
Invalid plans are rejected clearly; tests pass
Work is on a feature branch; no direct pushes to main
PR is reviewed, includes test output, and no secrets/recordings/personal data are committed

# Vaishnavi Savalagi

Overview
Foundation of the backend: app skeleton, health and readiness endpoints, a typed error envelope, request and correlation-ID middleware, session states with an in-memory repository, a mock session route and a one-command mock-mode launcher. Mock mode is the default; no paid API keys or credentials are needed.

Day-wise Implementation Plan

Day 1–2: Skeleton and endpoints
Create the app skeleton.
Add health and readiness endpoints.
Define the typed error envelope (code, message_safe_for_user, retryable, correlation_id, details_redacted).

Day 3–4: Middleware and sessions
Add request and correlation-ID middleware.
Implement session states (created, active, paused, stopping, completed, failed, expired) with an in-memory repository.
Add a mock session route.

Day 5–6: Launcher and route tests
Build a one-command mock-mode launcher.
Write route tests (health, readiness, errors, session route).

Deliverables
App skeleton with health and readiness endpoints
Typed error envelope
Request and correlation-ID middleware
Session states with in-memory repository and mock session route
One-command mock-mode launcher
Route tests with passing output
GitHub PR with test output; live demo (Day 7)

Acceptance Criteria
Health and readiness endpoints respond correctly
Errors use the typed envelope and expose no sensitive details
Every request carries a request ID and correlation ID
Session states and transitions are enforced; repository is in-memory
Launcher starts the backend in mock mode with one documented command
Route tests pass (normal, boundary and failure cases)
Work is on a feature branch; no direct pushes to main
PR is reviewed, includes test output, and no secrets/recordings/personal data are committed
Day 7 demo completed

# Sneha K Sawkar

Overview:

Foundation of the user interface: an accessible app shell with a mock-mode banner, session and microphone controls with permission states, a transcript timeline driven by fixture events and a typed API client with mock responses. Mock mode is the default; no paid API keys or credentials are needed.

Day-wise Implementation Plan

Day 1–2: App shell and session controls
Build an accessible app shell with a mock-mode banner.
Add session controls.

Day 3–4: Microphone states and transcript timeline
Implement microphone permission states.
Build the transcript timeline from fixture events.

Day 5–6: API client and component tests
Build a typed API client with mock responses.
Write component tests.

Deliverables
Accessible app shell with mock-mode banner and session controls
Microphone permission states
Transcript timeline rendered from fixture events
Typed API client with mock responses
Component tests with passing output
GitHub PR with test output; live demo (Day 7)

Acceptance Criteria
App shell is keyboard-navigable and accessible, with a visible mock-mode banner
Session controls work against mock data
Microphone permission states (e.g. prompt, granted, denied) are shown clearly
Transcript timeline renders fixture events in order
API client is typed and works with mock responses; error states are shown clearly
Component tests pass
Work is on a feature branch; no direct pushes to main
PR is reviewed, includes test output, and no secrets/recordings/personal data are committed
Day 7 demo completed