import unittest

from schemas.context import (
    SourceReference,
    ContextItem,
    ScreenContext,
    ReasoningRequest,
)
from reasoning.mock_reasoning import process_request, load_prompt


class TestMockReasoning(unittest.TestCase):

    def create_request(self):
        """Create a sample request with synthetic context."""

        source = SourceReference(
            source_id="source_001",
            source_type="text",
            description="Synthetic example",
        )

        item = ContextItem(
            item_id="item_001",
            content="The project uses Python.",
            source=source,
        )

        context = ScreenContext(
            context_id="context_001",
            items=[item],
            capture_enabled=False,
        )

        return ReasoningRequest(
            request_id="request_001",
            question="What language does the project use?",
            context=context,
        )

    def test_process_request_with_context(self):
        request = self.create_request()

        result = process_request(request)

        self.assertIn("The project uses Python.", result.answer)
        self.assertEqual(result.source_ids, ["source_001"])
        self.assertEqual(result.status, "success")

    def test_process_request_without_context(self):
        request = ReasoningRequest(
            request_id="request_002",
            question="What language does the project use?",
            context=ScreenContext(context_id="context_002"),
        )

        result = process_request(request)

        self.assertEqual(
            result.answer,
            "No context information is available.",
        )
        self.assertEqual(result.source_ids, [])
        self.assertEqual(result.status, "success")

    def test_invalid_request_rejected(self):
        request = ReasoningRequest(
            request_id="request_003",
            question="",
            context=ScreenContext(context_id="context_003"),
        )

        with self.assertRaises(ValueError):
            process_request(request)

    def test_multiple_context_items(self):
        source_1 = SourceReference("source_001", "text")
        source_2 = SourceReference("source_002", "text")

        item_1 = ContextItem(
            "item_001",
            "The project uses Python.",
            source_1,
        )
        item_2 = ContextItem(
            "item_002",
            "The project includes unit tests.",
            source_2,
        )

        request = ReasoningRequest(
            request_id="request_004",
            question="Describe the project.",
            context=ScreenContext(
                context_id="context_004",
                items=[item_1, item_2],
            ),
        )

        result = process_request(request)

        self.assertIn("The project uses Python.", result.answer)
        self.assertIn("The project includes unit tests.", result.answer)
        self.assertEqual(
            result.source_ids,
            ["source_001", "source_002"],
        )

    def test_repeated_requests_are_deterministic(self):
        request = self.create_request()

        first_result = process_request(request)
        second_result = process_request(request)

        self.assertEqual(first_result.answer, second_result.answer)
        self.assertEqual(first_result.source_ids, second_result.source_ids)

    def test_versioned_prompt_loads(self):
        prompt = load_prompt()

        self.assertEqual(prompt["prompt_name"], "context_reasoning")
        self.assertEqual(prompt["version"], "1.0.0")

    def test_prompt_contains_trusted_instructions(self):
        prompt = load_prompt()

        self.assertIsInstance(prompt["trusted_instructions"], list)
        self.assertTrue(prompt["trusted_instructions"])
        self.assertTrue(
            any(
                "untrusted data" in instruction.lower()
                for instruction in prompt["trusted_instructions"]
            )
        )

    def test_prompt_contains_required_fields(self):
        prompt = load_prompt()

        self.assertIn("input_fields", prompt)
        self.assertIn("output_format", prompt)


if __name__ == "__main__":
    unittest.main()