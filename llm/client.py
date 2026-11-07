"""Mock-first LLM adapter with timeout, retry and output validation."""

import queue
import re
import threading

from schemas.context import ReasoningRequest, ReasoningResult


class MockLLMClient:
    """Default local mock client. No API key or external service required."""

    def generate(self, request):
        return {
            "request_id": request.request_id,
            "answer": "Mock response: " + request.question,
            "source_ids": [
                item.source.source_id
                for item in request.context.items
            ],
            "status": "success",
        }


class LLMAdapter:
    def __init__(
        self,
        client=None,
        timeout_seconds=5,
        max_retries=2,
        max_output_length=2000,
    ):
        if timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")

        if max_retries < 0:
            raise ValueError("Retry count cannot be negative")

        if max_output_length < 1:
            raise ValueError("Output length must be positive")

        self.client = client if client is not None else MockLLMClient()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_output_length = max_output_length

    def validate_output(self, output, request):
        """Validate the structure, sources and basic output safety."""

        if not isinstance(output, dict):
            raise ValueError("LLM output must be a dictionary")

        required = {
            "request_id",
            "answer",
            "source_ids",
            "status",
        }

        if set(output.keys()) != required:
            raise ValueError("Missing or unexpected output fields")

        if output["request_id"] != request.request_id:
            raise ValueError("Request ID mismatch")

        answer = output["answer"]

        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Answer must be a non-empty string")

        if len(answer) > self.max_output_length:
            raise ValueError("Answer exceeds maximum length")

        if any(
            ord(char) < 32 and char not in "\n\t"
            for char in answer
        ):
            raise ValueError("Answer contains invalid control characters")

        # Reject potentially executable markup in generated answers.
        unsafe_pattern = r"<\s*(script|iframe|object|embed)\b|javascript\s*:"

        if re.search(unsafe_pattern, answer, re.IGNORECASE):
            raise ValueError("Unsafe executable markup detected")

        source_ids = output["source_ids"]

        if not isinstance(source_ids, list):
            raise ValueError("Source IDs must be a list")

        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Duplicate source IDs are not allowed")

        allowed_sources = {
            item.source.source_id
            for item in request.context.items
        }

        if any(
            not isinstance(source, str)
            or source not in allowed_sources
            for source in source_ids
        ):
            raise ValueError("Unknown or invalid source ID")

        if output["status"] != "success":
            raise ValueError("Invalid result status")

        result = ReasoningResult(**output)
        result.validate()

        return result

    def _call_with_timeout(self, request):
        """Run client in a daemon thread so a timeout does not block shutdown."""

        result_queue = queue.Queue(maxsize=1)

        def worker():
            try:
                result_queue.put(("success", self.client.generate(request)))
            except Exception as exc:
                result_queue.put(("error", exc))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        try:
            status, value = result_queue.get(
                timeout=self.timeout_seconds
            )
        except queue.Empty:
            raise TimeoutError("LLM request timed out")

        if status == "error":
            raise value

        return value

    def generate(self, request):
        """Generate a validated response with bounded timeout retries."""

        if not isinstance(request, ReasoningRequest):
            raise ValueError("Expected a ReasoningRequest")

        request.validate()

        for attempt in range(self.max_retries + 1):
            try:
                output = self._call_with_timeout(request)
                return self.validate_output(output, request)

            except TimeoutError:
                if attempt == self.max_retries:
                    raise TimeoutError(
                        "LLM request timed out after all retries"
                    )

        raise TimeoutError("LLM request failed")