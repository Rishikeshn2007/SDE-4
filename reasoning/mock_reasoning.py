"""Deterministic mock reasoning using a versioned prompt."""

import json
from pathlib import Path

from schemas.context import ReasoningRequest, ReasoningResult


PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "prompts"
    / "prompt_v1.json"
)


def load_prompt() -> dict:
    """Load and validate the versioned prompt specification."""

    with PROMPT_PATH.open("r", encoding="utf-8") as prompt_file:
        prompt = json.load(prompt_file)

    required_fields = {
        "prompt_name",
        "version",
        "trusted_instructions",
        "input_fields",
        "output_format",
    }

    missing_fields = required_fields.difference(prompt)

    if missing_fields:
        raise ValueError(
            f"Prompt is missing required fields: {sorted(missing_fields)}"
        )

    if not isinstance(prompt["trusted_instructions"], list):
        raise ValueError("trusted_instructions must be a list")

    if not all(
        isinstance(instruction, str) and instruction.strip()
        for instruction in prompt["trusted_instructions"]
    ):
        raise ValueError(
            "Each trusted instruction must be a non-empty string"
        )

    return prompt


def process_request(request: ReasoningRequest) -> ReasoningResult:
    """
    Process a reasoning request using the supplied context.

    The versioned prompt provides the trusted instructions.
    This mock implementation remains deterministic and does not
    execute context text as instructions.
    """

    request.validate()

    # Load the prompt specification before processing the request.
    prompt = load_prompt()

    # Return a predictable answer when no context is available.
    if not request.context.items:
        result = ReasoningResult(
            request_id=request.request_id,
            answer="No context information is available.",
            source_ids=[],
            status="success",
        )
        result.validate()
        return result

    # Collect context information in the supplied order.
    context_parts = []
    source_ids = []

    for item in request.context.items:
        context_parts.append(item.content)

        if item.source.source_id not in source_ids:
            source_ids.append(item.source.source_id)

    # Generate a predictable response from the supplied context.
    answer = "Context: " + " ".join(context_parts)

    result = ReasoningResult(
        request_id=request.request_id,
        answer=answer,
        source_ids=source_ids,
        status="success",
    )

    result.validate()
    return result