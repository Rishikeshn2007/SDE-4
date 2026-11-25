"""Tests for sensitive information redaction."""

import unittest

from observations.privacy_redactor import (
    PrivacyRedactor,
    redact_sensitive_text,
)


class TestPrivacyRedactor(unittest.TestCase):

    def test_redacts_email_address(self):
        text = "Contact user@example.com for support."

        result = PrivacyRedactor.redact(text)

        self.assertNotIn("user@example.com", result)
        self.assertIn("[REDACTED_EMAIL]", result)

    def test_redacts_bearer_token(self):
        text = "Authorization: Bearer abcdefghijklmnop123456"

        result = PrivacyRedactor.redact(text)

        self.assertNotIn("abcdefghijklmnop123456", result)
        self.assertIn("[REDACTED_TOKEN]", result)

    def test_redacts_api_key_assignment(self):
        text = "api_key=super_secret_key_123"

        result = PrivacyRedactor.redact(text)

        self.assertNotIn("super_secret_key_123", result)
        self.assertIn("[REDACTED_SECRET]", result)

    def test_redacts_password_assignment(self):
        text = "password: my_private_password"

        result = PrivacyRedactor.redact(text)

        self.assertNotIn("my_private_password", result)
        self.assertIn("[REDACTED_SECRET]", result)

    def test_redacts_common_service_token(self):
        token = "ghp_" + ("A" * 30)
        text = f"GitHub token: {token}"

        result = PrivacyRedactor.redact(text)

        self.assertNotIn(token, result)
        self.assertIn("[REDACTED_TOKEN]", result)

    def test_preserves_normal_text(self):
        text = "The project uses Python and automated tests."

        result = PrivacyRedactor.redact(text)

        self.assertEqual(result, text)

    def test_redaction_is_idempotent(self):
        text = "Email: user@example.com"

        first_result = redact_sensitive_text(text)
        second_result = redact_sensitive_text(first_result)

        self.assertEqual(first_result, second_result)

    def test_rejects_non_string_input(self):
        with self.assertRaises(TypeError):
            PrivacyRedactor.redact(None)


if __name__ == "__main__":
    unittest.main()