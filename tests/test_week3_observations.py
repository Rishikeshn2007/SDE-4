"""Tests for Week 3 observation management."""

import unittest
from datetime import datetime, timedelta, timezone

from schemas.context import ContextItem, SourceReference
from observations.observation_builder import (
    ObservationInput,
    ObservationBuilder,
)
from observations.consent_manager import ConsentManager


class TestWeek3Observations(unittest.TestCase):

    def setUp(self):
        self.now = datetime.now(timezone.utc)

        self.item = ContextItem(
            item_id="item_001",
            content="The project uses Python.",
            source=SourceReference(
                source_id="source_001",
                source_type="synthetic",
                description="Synthetic test observation",
            ),
        )

        self.builder = ObservationBuilder(max_age_seconds=3600)

    def test_timestamped_observation(self):
        entry = ObservationInput(self.item, self.now)

        result = self.builder.build([entry], now=self.now)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source_id, "source_001")
        self.assertEqual(result[0].timestamp, self.now)

    def test_stale_observation_is_dropped(self):
        old_time = self.now - timedelta(hours=2)

        entry = ObservationInput(self.item, old_time)

        result = self.builder.build([entry], now=self.now)

        self.assertEqual(result, [])

    def test_duplicate_observation_is_dropped(self):
        entry = ObservationInput(self.item, self.now)

        result = self.builder.build(
            [entry, entry],
            now=self.now,
        )

        self.assertEqual(len(result), 1)

    def test_future_timestamp_rejected(self):
        future_time = self.now + timedelta(minutes=5)

        entry = ObservationInput(self.item, future_time)

        with self.assertRaises(ValueError):
            self.builder.build([entry], now=self.now)

    def test_naive_timestamp_rejected(self):
        naive_time = datetime.now()

        entry = ObservationInput(self.item, naive_time)

        with self.assertRaises(ValueError):
            self.builder.build([entry], now=self.now)

    def test_invalid_entry_rejected(self):
        with self.assertRaises(ValueError):
            self.builder.build(["invalid"], now=self.now)

    def test_consent_disabled_by_default(self):
        manager = ConsentManager()

        self.assertFalse(manager.consent_enabled)

    def test_consent_required_before_adding(self):
        manager = ConsentManager()

        with self.assertRaises(PermissionError):
            manager.add_observation(self.item)

    def test_withdrawal_clears_pending_observations(self):
        manager = ConsentManager()
        manager.enable_consent()
        manager.add_observation(self.item)

        manager.withdraw_consent()

        self.assertFalse(manager.consent_enabled)
        self.assertEqual(manager.get_pending_observations(), [])

    def test_consent_can_be_enabled_again(self):
        manager = ConsentManager()

        manager.enable_consent()
        manager.withdraw_consent()
        manager.enable_consent()

        self.assertTrue(manager.consent_enabled)


if __name__ == "__main__":
    unittest.main()