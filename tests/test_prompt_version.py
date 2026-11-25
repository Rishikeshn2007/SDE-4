"""Tests for prompt version tracking."""

import unittest

from prompts.prompt_version import (
    PromptVersion,
    PromptVersionRegistry,
)


class TestPromptVersionRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = PromptVersionRegistry()

    def test_register_prompt_version(self):
        result = self.registry.register(
            "v1",
            "Initial grounded reasoning prompt",
        )

        self.assertIsInstance(result, PromptVersion)
        self.assertEqual(result.version, "v1")

    def test_retrieve_prompt_version(self):
        self.registry.register("v1", "Initial prompt")

        result = self.registry.get("v1")

        self.assertEqual(result.description, "Initial prompt")

    def test_unknown_version_returns_none(self):
        self.assertIsNone(self.registry.get("v99"))

    def test_duplicate_version_rejected(self):
        self.registry.register("v1", "Initial prompt")

        with self.assertRaises(ValueError):
            self.registry.register("v1", "Duplicate prompt")

    def test_empty_version_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register("", "Initial prompt")

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register("v1", "")

    def test_list_versions(self):
        self.registry.register("v1", "Initial prompt")
        self.registry.register("v2", "Updated prompt")

        versions = self.registry.list_versions()

        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].version, "v1")
        self.assertEqual(versions[1].version, "v2")

    def test_latest_version(self):
        self.registry.register("v1", "Initial prompt")
        self.registry.register("v2", "Updated prompt")

        self.assertEqual(
            self.registry.latest().version,
            "v2",
        )

    def test_latest_when_empty(self):
        self.assertIsNone(self.registry.latest())


if __name__ == "__main__":
    unittest.main()