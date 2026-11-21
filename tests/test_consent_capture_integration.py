"""Integration tests for consent, capture, vision and observations."""

import unittest
from datetime import datetime, timezone

from adapters.capture import CaptureAdapter, SyntheticFrame
from adapters.vision import MockVisionAdapter
from observations.consent_manager import ConsentManager
from observations.observation_builder import (
    ObservationBuilder,
    ObservationInput,
)
from schemas.context import ContextItem, SourceReference


class TestConsentCaptureIntegration(unittest.TestCase):

    def setUp(self):
        self.capture = CaptureAdapter(
            opt_in=False,
            sample_every_n=1,
            max_frame_bytes=1024,
        )

        self.consent = ConsentManager(
            capture_adapter=self.capture
        )

        self.vision = MockVisionAdapter()
        self.builder = ObservationBuilder(max_age_seconds=3600)

        self.frame = SyntheticFrame(
            frame_id="synthetic_frame_001",
            data=b"The project uses Python.",
        )

    def test_capture_starts_disabled(self):
        self.assertFalse(self.capture.opt_in)
        self.assertFalse(self.consent.consent_enabled)

    def test_enabling_consent_enables_capture(self):
        self.consent.enable_consent()

        self.assertTrue(self.consent.consent_enabled)
        self.assertTrue(self.capture.opt_in)

    def test_capture_works_after_consent(self):
        self.consent.enable_consent()

        result = self.capture.process_frame(self.frame)

        self.assertEqual(result, self.frame)

    def test_complete_capture_vision_observation_flow(self):
        self.consent.enable_consent()

        captured_frame = self.capture.process_frame(self.frame)
        extracted_text = self.vision.extract_text(captured_frame)

        item = ContextItem(
            item_id="item_001",
            content=extracted_text,
            source=SourceReference(
                source_id=captured_frame.frame_id,
                source_type="synthetic",
                description="Text extracted from a synthetic frame",
            ),
        )

        now = datetime.now(timezone.utc)

        observations = self.builder.build(
            [ObservationInput(item=item, timestamp=now)],
            now=now,
        )

        self.assertEqual(len(observations), 1)
        self.assertEqual(
            observations[0].content,
            "The project uses Python.",
        )
        self.assertEqual(
            observations[0].source_id,
            "synthetic_frame_001",
        )

        self.consent.add_observation(observations[0])

        pending = self.consent.get_pending_observations()

        self.assertEqual(len(pending), 1)
        self.assertEqual(
            pending[0].source_id,
            "synthetic_frame_001",
        )

    def test_withdrawal_disables_capture(self):
        self.consent.enable_consent()
        self.consent.withdraw_consent()

        self.assertFalse(self.consent.consent_enabled)
        self.assertFalse(self.capture.opt_in)

    def test_withdrawal_clears_pending_observations(self):
        self.consent.enable_consent()
        self.consent.add_observation("synthetic observation")

        self.consent.withdraw_consent()

        self.assertEqual(
            self.consent.get_pending_observations(),
            [],
        )

    def test_capture_rejected_after_withdrawal(self):
        self.consent.enable_consent()
        self.consent.withdraw_consent()

        with self.assertRaises(PermissionError):
            self.capture.process_frame(self.frame)


if __name__ == "__main__":
    unittest.main()