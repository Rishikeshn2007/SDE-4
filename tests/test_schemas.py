import unittest

from schemas.context import (
    SourceReference,
    ContextItem,
    ScreenContext,
    ReasoningRequest,
    ReasoningResult,
)


class TestSchemas(unittest.TestCase):

    def test_valid_context(self):
        source = SourceReference(
            source_id="source_001",
            source_type="text",
            description="Example source",
        )

        item = ContextItem(
            item_id="item_001",
            content="The project uses Python.",
            source=source,
        )

        context = ScreenContext(
            context_id="context_001",
            items=[item],
        )

        context.validate()

    def test_empty_question_rejected(self):
        context = ScreenContext(context_id="context_001")

        request = ReasoningRequest(
            request_id="request_001",
            question="",
            context=context,
        )

        with self.assertRaises(ValueError):
            request.validate()

    def test_screen_capture_disabled(self):
        context = ScreenContext(
            context_id="context_001",
            capture_enabled=True,
        )

        with self.assertRaises(ValueError):
            context.validate()

    def test_valid_result(self):
        result = ReasoningResult(
            request_id="request_001",
            answer="The project uses Python.",
            source_ids=["source_001"],
        )

        result.validate()

    def test_empty_source_id_rejected(self):
        source = SourceReference(
            source_id="",
            source_type="text",
        )

        with self.assertRaises(ValueError):
            source.validate()

    def test_empty_context_is_valid(self):
        context = ScreenContext(context_id="context_001")
        context.validate()

    def test_invalid_source_type_rejected(self):
        source = SourceReference(
            source_id="source_001",
            source_type="",
        )

        with self.assertRaises(ValueError):
            source.validate()

    def test_invalid_result_status_rejected(self):
        result = ReasoningResult(
            request_id="request_001",
            answer="Example answer",
            status="unknown",
        )

        with self.assertRaises(ValueError):
            result.validate()


if __name__ == "__main__":
    unittest.main()