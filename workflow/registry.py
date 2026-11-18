from workflow.schemas import ToolSpec
from workflow.mock_tools import MOCK_TOOLS


TOOL_REGISTRY = {
    "mock_calculator": ToolSpec(
        name="mock_calculator",
        required_arguments=("a", "b"),
        allowed_arguments=("a", "b"),
        permission_scope="safe",
        idempotent=True,
        timeout_seconds=5.0,
    ),
    "mock_note_preview": ToolSpec(
        name="mock_note_preview",
        required_arguments=("title", "content"),
        allowed_arguments=("title", "content"),
        permission_scope="safe",
        idempotent=True,
        timeout_seconds=5.0,
    ),
}


def validate_tool_call(step):
    if step.tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {step.tool_name}")

    if step.tool_name not in MOCK_TOOLS:
        raise ValueError(f"Tool is not executable: {step.tool_name}")

    spec = TOOL_REGISTRY[step.tool_name]

    if not isinstance(step.inputs, dict):
        raise ValueError("Step inputs must be a dictionary")

    missing = set(spec.required_arguments) - set(step.inputs)
    if missing:
        raise ValueError(
            f"Missing arguments for {step.tool_name}: "
            f"{', '.join(sorted(missing))}"
        )

    unexpected = set(step.inputs) - set(spec.allowed_arguments)
    if unexpected:
        raise ValueError(
            f"Unexpected arguments for {step.tool_name}: "
            f"{', '.join(sorted(unexpected))}"
        )

    if step.permission_scope != spec.permission_scope:
        raise ValueError(
            f"Permission denied for {step.tool_name}: "
            f"required scope is '{spec.permission_scope}'"
        )

    return spec
