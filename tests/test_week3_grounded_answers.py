"""Tests for grounded answers and source references."""

import unittest

from schemas.context import (
    ContextItem,
    SourceReference,
    ScreenContext,
    ReasoningRequest,
)

from reasoning.grounded_answer import GroundedAnswerGenerator


class TestGroundedAnswers(unittest.TestCase):

    def setUp(self):
        self.generator = GroundedAnswerGenerator()

        self.item1 = ContextItem(
            item_id="item_001",
            content="The project uses Python.",
            source=SourceReference(
                source_id="source_001",
                source_type="synthetic",
                description="Programming language evidence",
            ),
        )

        self.item2 = ContextItem(
            item_id="item_002",
            content="The project includes automated unit tests.",
            source=SourceReference(
                source_id="source_002",
                source_type="synthetic",
                description="Testing evidence",
            ),
        )

    def make_request(self, question, items):
        context = ScreenContext(
            context_id="context_001",
            items=items,
            capture_enabled=False,
        )

        return ReasoningRequest(
            request_id="request_001",
            question=question,
            context=context,
        )

    def test_grounded_answer(self):
        request = self.make_request(
            "What language does the project use?",
            [self.item1],
        )

        result = self.generator.generate(request)

        self.assertIn("Python", result.answer)
        self.assertEqual(result.source_ids, ["source_001"])

    def test_answer_contains_matching_evidence(self):
        request = self.make_request(
            "What testing is included?",
            [self.item1, self.item2],
        )

        result = self.generator.generate(request)

        self.assertIn("automated unit tests", result.answer)
        self.assertEqual(result.source_ids, ["source_002"])

    def test_no_evidence_response(self):
        request = self.make_request(
            "What database does the project use?",
            [self.item1, self.item2],
        )

        result = self.generator.generate(request)

        self.assertEqual(
            result.answer,
            self.generator.NO_EVIDENCE_MESSAGE,
        )
        self.assertEqual(result.source_ids, [])

    def test_empty_context_returns_no_evidence(self):
        request = self.make_request(
            "What language does the project use?",
            [],
        )

        result = self.generator.generate(request)

        self.assertEqual(result.source_ids, [])
        self.assertIn("not have enough evidence", result.answer)

    def test_invalid_request_rejected(self):
        with self.assertRaises(ValueError):
            self.generator.generate("invalid request")

    def test_multiple_sources_returned(self):
        request = self.make_request(
            "Tell me about the project",
            [self.item1, self.item2],
        )

        result = self.generator.generate(request)

        self.assertEqual(
            result.source_ids,
            ["source_001", "source_002"],
        )

    def test_duplicate_source_ids_not_repeated(self):
        item = ContextItem(
            item_id="item_003",
            content="The project uses Java.",
            source=SourceReference(
                source_id="source_001",
                source_type="synthetic",
            ),
        )

        request = self.make_request(
            "What language does the project use?",
            [self.item1, item],
        )

        result = self.generator.generate(request)

        self.assertEqual(result.source_ids, ["source_001"])

    def test_result_schema_is_valid(self):
        request = self.make_request(
            "What language does the project use?",
            [self.item1],
        )

        result = self.generator.generate(request)

        result.validate()
        self.assertEqual(result.status, "success")


if __name__ == "__main__":
    unittest.main()