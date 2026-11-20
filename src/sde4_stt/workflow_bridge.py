"""
Voice-to-Workflow Bridge (Week 3, D19-21 Integration).

Connects transcribed text from the STT pipeline to canonical Week 4 workflow
planning and execution, enforcing consequential approval gates and publishing
lifecycle events to the W5 backend event stream.

Flow:
    Audio Chunks -> STT Orchestrator -> Final Transcript
    -> VoiceWorkflowBridge.reason_and_plan()
    -> VoiceWorkflowBridge.execute() [pauses at Approval Gate if consequential]
    -> User / Consumer grants approval
    -> VoiceWorkflowBridge.execute(approvals={...}) -> Succeeded
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from workflow.executor import execute_plan
from workflow.schemas import (
    ApprovalRequest,
    WorkflowPlan,
    WorkflowResult,
    WorkflowState,
    WorkflowStep,
)

from sde4_stt.event_bridge import EventBridgePublisher


# Keywords that imply consequential / sensitive actions requiring human approval
CONSEQUENTIAL_KEYWORDS = {
    "send",
    "publish",
    "delete",
    "remove",
    "drop",
    "execute",
    "format",
    "deploy",
    "submit",
    "transfer",
}


class VoiceWorkflowBridge:
    """Bridges STT transcripts to workflow generation, execution, and W5 event streaming.

    Args:
        event_publisher: Optional ``EventBridgePublisher`` for publishing
            lifecycle events to the backend event stream.
    """

    def __init__(
        self,
        event_publisher: Optional[EventBridgePublisher] = None,
    ) -> None:
        self._event_publisher = event_publisher

    @property
    def event_publisher(self) -> Optional[EventBridgePublisher]:
        return self._event_publisher

    def reason_and_plan(
        self,
        session_id: str,
        transcript_text: str,
        force_consequential: Optional[bool] = None,
    ) -> WorkflowPlan:
        """Analyze transcribed speech intent and build a validated WorkflowPlan.

        Args:
            session_id: The active session identifier.
            transcript_text: Recognized speech text.
            force_consequential: Explicitly override consequential flag.

        Returns:
            A canonical ``WorkflowPlan`` containing one or more ``WorkflowStep`` objects.
        """
        text_lower = transcript_text.lower().strip()
        steps: List[WorkflowStep] = []

        # Determine if action is consequential
        is_consequential = (
            force_consequential
            if force_consequential is not None
            else any(kw in text_lower.split() for kw in CONSEQUENTIAL_KEYWORDS)
        )

        # Mathematical calculation intent
        if any(w in text_lower for w in ("calculate", "sum", "add", "plus", "+")):
            numbers = [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", text_lower)]
            a = numbers[0] if len(numbers) > 0 else 10.0
            b = numbers[1] if len(numbers) > 1 else 20.0
            steps.append(
                WorkflowStep(
                    step_id="step_calc_1",
                    tool_name="mock_calculator",
                    inputs={"a": a, "b": b},
                    consequential=is_consequential,
                )
            )
        # Note preview or drafting intent (default fallback)
        else:
            title = "Voice Note"
            content = transcript_text.strip() or "Empty transcript note"
            steps.append(
                WorkflowStep(
                    step_id="step_note_1",
                    tool_name="mock_note_preview",
                    inputs={"title": title, "content": content},
                    consequential=is_consequential,
                )
            )

        plan = WorkflowPlan(
            plan_id=f"plan_{session_id}",
            steps=steps,
        )
        return plan

    def execute(
        self,
        plan: WorkflowPlan,
        session_id: str,
        approvals: Optional[Dict[str, bool]] = None,
    ) -> WorkflowResult:
        """Execute a WorkflowPlan, enforcing approval gates and publishing status events.

        Args:
            plan: The ``WorkflowPlan`` to execute.
            session_id: Session identifier to attach to backend events.
            approvals: Dict mapping step_id to boolean approval decisions.

        Returns:
            ``WorkflowResult`` containing state, outputs, or pending approval requests.
        """
        approvals = approvals or {}
        result = execute_plan(plan, approvals=approvals)

        # Publish state transition to W5 backend event stream if publisher configured
        if self._event_publisher is not None:
            event_type = f"workflow_{result.state.value}"
            payload: Dict[str, Any] = {
                "session_id": session_id,
                "plan_id": result.plan_id,
                "state": result.state.value,
            }
            if result.state == WorkflowState.AWAITING_APPROVAL and result.approval_request:
                payload["step_id"] = result.approval_request.step_id
                payload["description"] = result.approval_request.description
            elif result.state == WorkflowState.SUCCEEDED:
                payload["step_results"] = result.step_results
            elif result.state == WorkflowState.FAILED:
                payload["error"] = result.error

            # Deliver to W5 event sink
            try:
                self._event_publisher._publish_fn(session_id, event_type, payload)
                self._event_publisher._publish_count += 1
            except Exception as exc:
                self._event_publisher._publish_errors.append(exc)

        return result


__all__ = ["VoiceWorkflowBridge", "CONSEQUENTIAL_KEYWORDS"]
