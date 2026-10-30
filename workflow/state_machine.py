from workflow.schemas import WorkflowState


ALLOWED_TRANSITIONS = {
    WorkflowState.DRAFT: {
        WorkflowState.AWAITING_APPROVAL,
        WorkflowState.RUNNING,
        WorkflowState.CANCELLED,
        WorkflowState.FAILED,
    },
    WorkflowState.AWAITING_APPROVAL: {
        WorkflowState.RUNNING,
        WorkflowState.PAUSED,
        WorkflowState.CANCELLED,
        WorkflowState.FAILED,
    },
    WorkflowState.RUNNING: {
        WorkflowState.AWAITING_APPROVAL,
        WorkflowState.PAUSED,
        WorkflowState.SUCCEEDED,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.PAUSED: {
        WorkflowState.RUNNING,
        WorkflowState.AWAITING_APPROVAL,
        WorkflowState.CANCELLED,
        WorkflowState.FAILED,
    },
    WorkflowState.SUCCEEDED: set(),
    WorkflowState.FAILED: set(),
    WorkflowState.CANCELLED: set(),
}


def transition(current, new_state):
    if new_state not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(
            f"Illegal transition: {current.value} "
            f"-> {new_state.value}"
        )

    return new_state