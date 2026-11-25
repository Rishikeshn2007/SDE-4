"""Privacy tests for the legacy mock reasoning and LLM adapter paths."""

import unittest

from schemas.context import (
    ContextItem,
    ReasoningRequest,
    ScreenContext,
    SourceReference,
)
from reasoning.mock_reasoning import (
    PROMPT_VERSION_REGISTRY,
    process_request,
)
from llm.client import LLMAdapter


def make_request(question, content):
    source = SourceReference(
        source_id="source_privacy_001",
        source_type="synthetic",
        description="Synthetic privacy test source",
    )
    item = ContextItem(
        item_id="item_privacy_001",
        content=content,
        source=source,
    )
    context = ScreenContext(
        context_id="context_privacy_001",
        items=[item],
        capture_enabled=False,
    )
    return ReasoningRequest(
        request_id="request_privacy_001",
        question=question,
        context=context,
    )


class EchoClient:
    """Test client that echoes received request data."""

    def __init__(self):
        self.received_request = None

    def generate(self, request):
        self.received_request = request
        return {
            "request_id": request.request_id,
            "answer": (
                request.question + " " +
                " ".join(item.content for item in request.context.items)
            ),
            "source_ids": [
                item.source.source_id
                for item in request.context.items
            ],
            "status": "success",
        }


class TestLegacyPrivacyPaths(unittest.TestCase):

    def test_mock_reasoning_redacts_context_and_keeps_source(self):
        request = make_request(
            "Summarize the context",
            "Contact user@example.com using api_key=secret-value",
        )

        result = process_request(request)

        self.assertNotIn("user@example.com", result.answer)
        self.assertNotIn("secret-value", result.answer)
        self.assertIn("source_privacy_001", result.source_ids)

    def test_llm_client_receives_redacted_copy(self):
        request = make_request(
            "Contact user@example.com",
            "The api_key=secret-value is configured",
        )
        original_question = request.question
        original_content = request.context.items[0].content
        client = EchoClient()

        result = LLMAdapter(client=client).generate(request)

        self.assertIsNotNone(client.received_request)
        self.assertNotIn(
            "user@example.com",
            client.received_request.question,
        )
        self.assertNotIn(
            "secret-value",
            client.received_request.context.items[0].content,
        )
        self.assertNotIn("user@example.com", result.answer)
        self.assertNotIn("secret-value", result.answer)

        # The caller's original request must remain unchanged.
        self.assertEqual(request.question, original_question)
        self.assertEqual(
            request.context.items[0].content,
            original_content,
        )

    def test_llm_source_validation_uses_original_source_ids(self):
        request = make_request(
            "Summarize this",
            "A normal synthetic context item",
        )

        result = LLMAdapter().generate(request)

        self.assertEqual(
            result.source_ids,
            ["source_privacy_001"],
        )

    def test_loaded_prompt_is_registered(self):
        request = make_request("Summarize this", "Synthetic context")
        process_request(request)

        registered = PROMPT_VERSION_REGISTRY.get("1.0.0")

        self.assertIsNotNone(registered)
        self.assertTrue(registered.description)


if __name__ == "__main__":
    unittest.main()
