import time
import unittest
from datetime import datetime, timedelta, timezone

from adapters.capture import CaptureAdapter, SyntheticFrame
from adapters.vision import MockVisionAdapter
from context_builder.builder import ContextBuilder, ContextEntry
from llm.client import LLMAdapter
from schemas.context import (
    ContextItem,
    ScreenContext,
    SourceReference,
    ReasoningRequest,
)


class Week2Tests(unittest.TestCase):

    def make_item(self, item_id, content, source_id):
        source = SourceReference(
            source_id=source_id,
            source_type="synthetic",
            description="Test source"
        )
        return ContextItem(
            item_id=item_id,
            content=content,
            source=source
        )

    def make_request(self):
        item = self.make_item("1", "Python is used", "s1")
        context = ScreenContext(
            context_id="ctx_test",
            items=[item],
            capture_enabled=False
        )
        return ReasoningRequest(
            request_id="request_test",
            question="Which language is used?",
            context=context
        )

    def test_capture_disabled_by_default(self):
        adapter = CaptureAdapter()
        self.assertFalse(adapter.opt_in)

    def test_capture_requires_opt_in(self):
        adapter = CaptureAdapter()
        frame = SyntheticFrame("frame1", b"Python")
        with self.assertRaises(PermissionError):
            adapter.process_frame(frame)

    def test_frame_size_limit(self):
        adapter = CaptureAdapter(opt_in=True, max_frame_bytes=3)
        frame = SyntheticFrame("frame1", b"Python")
        with self.assertRaises(ValueError):
            adapter.process_frame(frame)

    def test_frame_sampling(self):
        adapter = CaptureAdapter(opt_in=True, sample_every_n=2)
        frame1 = SyntheticFrame("frame1", b"One")
        frame2 = SyntheticFrame("frame2", b"Two")
        self.assertIsNotNone(adapter.process_frame(frame1))
        self.assertIsNone(adapter.process_frame(frame2))

    def test_mock_vision(self):
        vision = MockVisionAdapter()
        frame = SyntheticFrame("frame1", b"Python")
        self.assertEqual(vision.extract_text(frame), "Python")

    def test_context_builder(self):
        item = self.make_item("1", "Python programming", "s1")
        entry = ContextEntry(item, datetime.now(timezone.utc))
        builder = ContextBuilder()
        result = builder.build("ctx1", [entry], query="Python")
        self.assertEqual(len(result.items), 1)

    def test_stale_context_filtering(self):
        item = self.make_item("1", "Old information", "s1")
        entry = ContextEntry(
            item,
            datetime.now(timezone.utc) - timedelta(days=5)
        )
        builder = ContextBuilder(max_age_seconds=3600)
        result = builder.build("ctx1", [entry])
        self.assertEqual(len(result.items), 0)

    def test_token_budget(self):
        item = self.make_item("1", "Python Java C++ JavaScript", "s1")
        entry = ContextEntry(item, datetime.now(timezone.utc))
        builder = ContextBuilder(token_budget=2)
        result = builder.build("ctx1", [entry])
        self.assertEqual(len(result.items), 0)

    def test_mock_llm(self):
        adapter = LLMAdapter()
        result = adapter.generate(self.make_request())
        self.assertEqual(result.status, "success")
        self.assertIn("Mock response", result.answer)

    def test_malformed_output_rejected(self):
        class BadClient:
            def generate(self, request):
                return {"wrong_field": "invalid"}

        adapter = LLMAdapter(client=BadClient())
        with self.assertRaises(ValueError):
            adapter.generate(self.make_request())

    def test_unknown_source_rejected(self):
        class BadSourceClient:
            def generate(self, request):
                return {
                    "request_id": request.request_id,
                    "answer": "Python is used.",
                    "source_ids": ["unknown_source"],
                    "status": "success"
                }

        adapter = LLMAdapter(client=BadSourceClient())
        with self.assertRaises(ValueError):
            adapter.generate(self.make_request())

    def test_llm_timeout_retry_success(self):
        class SlowFirstClient:
            def __init__(self):
                self.calls = 0

            def generate(self, request):
                self.calls += 1
                if self.calls == 1:
                    time.sleep(0.15)

                return {
                    "request_id": request.request_id,
                    "answer": "Python is used.",
                    "source_ids": ["s1"],
                    "status": "success"
                }

        client = SlowFirstClient()
        adapter = LLMAdapter(
            client=client,
            timeout_seconds=0.03,
            max_retries=2
        )
        result = adapter.generate(self.make_request())
        self.assertEqual(result.status, "success")
        self.assertEqual(client.calls, 2)

    def test_llm_timeout_after_all_retries(self):
        class SlowClient:
            def generate(self, request):
                time.sleep(0.2)
                return {}

        adapter = LLMAdapter(
            client=SlowClient(),
            timeout_seconds=0.02,
            max_retries=1
        )

        with self.assertRaises(TimeoutError):
            adapter.generate(self.make_request())

    def test_unsafe_markup_rejected(self):
        class UnsafeClient:
            def generate(self, request):
                return {
                    "request_id": request.request_id,
                    "answer": "<script>alert('test')</script>",
                    "source_ids": [],
                    "status": "success"
                }

        adapter = LLMAdapter(client=UnsafeClient())
        with self.assertRaises(ValueError):
            adapter.generate(self.make_request())

    def test_duplicate_sources_rejected(self):
        class DuplicateSourceClient:
            def generate(self, request):
                return {
                    "request_id": request.request_id,
                    "answer": "Python is used.",
                    "source_ids": ["s1", "s1"],
                    "status": "success"
                }

        adapter = LLMAdapter(client=DuplicateSourceClient())
        with self.assertRaises(ValueError):
            adapter.generate(self.make_request())


if __name__ == "__main__":
    unittest.main()