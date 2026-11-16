"""Tests for consent and capture adapter integration."""

import unittest

from adapters.capture import CaptureAdapter, SyntheticFrame
from observations.consent_manager import ConsentManager


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

        self.frame = SyntheticFrame(
            frame_id="synthetic_frame_001",
            data=b"synthetic test data",
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