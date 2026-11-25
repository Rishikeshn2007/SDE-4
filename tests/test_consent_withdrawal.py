"""Tests for consent withdrawal and context clearing."""

import unittest

from adapters.capture import CaptureAdapter, SyntheticFrame
from observations.consent_manager import ConsentManager


class TestConsentWithdrawal(unittest.TestCase):

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

    def test_consent_is_disabled_by_default(self):
        with self.assertRaises(PermissionError):
            self.consent.add_observation("test observation")

    def test_enable_consent_allows_observations(self):
        self.consent.enable_consent()

        self.consent.add_observation("Python project context")

        self.assertEqual(
            self.consent.get_pending_observations(),
            ["Python project context"],
        )

    def test_withdrawal_clears_pending_observations(self):
        self.consent.enable_consent()
        self.consent.add_observation("Synthetic observation")

        self.consent.withdraw_consent()

        self.assertEqual(
            self.consent.get_pending_observations(),
            [],
        )

    def test_withdrawal_stops_new_capture(self):
        self.consent.enable_consent()
        self.consent.withdraw_consent()

        with self.assertRaises(PermissionError):
            self.capture.process_frame(self.frame)

    def test_observations_rejected_after_withdrawal(self):
        self.consent.enable_consent()
        self.consent.withdraw_consent()

        with self.assertRaises(PermissionError):
            self.consent.add_observation("New observation")

    def test_clear_removes_pending_observations(self):
        self.consent.enable_consent()
        self.consent.add_observation("Observation one")
        self.consent.add_observation("Observation two")

        self.consent.clear()

        self.assertEqual(
            self.consent.get_pending_observations(),
            [],
        )

    def test_empty_observation_is_rejected(self):
        self.consent.enable_consent()

        with self.assertRaises(ValueError):
            self.consent.add_observation(None)


if __name__ == "__main__":
    unittest.main()