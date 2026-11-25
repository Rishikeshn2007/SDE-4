"""Deterministic mock reasoning using a versioned prompt."""

import json
from pathlib import Path

from schemas.context import ReasoningRequest, ReasoningResult
from observations.privacy_redactor import PrivacyRedactor
from prompts.prompt_version import PromptVersionRegistry


PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "prompts"
    / "prompt_v1.json"
)

PROMPT_VERSION_REGISTRY = PromptVersionRegistry()


def load_prompt() -> dict:
    """Load, validate, and register the versioned prompt specification."""

    with PROMPT_PATH.open("r", encoding="utf-8") as prompt_file:
        prompt = json.load(prompt_file)

    required_fields = {
        "prompt_name",
        "version",
        "description",
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

    version = prompt["version"]
    if PROMPT_VERSION_REGISTRY.get(version) is None:
        PROMPT_VERSION_REGISTRY.register(
            version,
            prompt["description"],
        )

    return prompt


def process_request(request: ReasoningRequest) -> ReasoningResult:
    """
    Process a reasoning request using the supplied context.

    Context is treated as untrusted data and redacted before it is
    included in the generated answer.
    """

    if not isinstance(request, ReasoningRequest):
        raise ValueError("Expected a ReasoningRequest")

    request.validate()
    load_prompt()

    if not request.context.items:
        result = ReasoningResult(
            request_id=request.request_id,
            answer="No context information is available.",
            source_ids=[],
            status="success",
        )
        result.validate()
        return result

    context_parts = []
    source_ids = []

    for item in request.context.items:
        safe_content = PrivacyRedactor.redact(item.content)
        context_parts.append(safe_content)

        if item.source.source_id not in source_ids:
            source_ids.append(item.source.source_id)

    answer = "Context: " + " ".join(context_parts)

    result = ReasoningResult(
        request_id=request.request_id,
        answer=answer,
        source_ids=source_ids,
        status="success",
    )

    result.validate()
    return result
