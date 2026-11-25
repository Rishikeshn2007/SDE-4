"""Redact common sensitive information from text before processing."""

import re


class PrivacyRedactor:
    """Masks email addresses, passwords, API keys, and access tokens."""

    EMAIL_PATTERN = re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    )

    BEARER_PATTERN = re.compile(
        r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
        re.IGNORECASE,
    )

    SECRET_ASSIGNMENT_PATTERN = re.compile(
        r"\b(api[_-]?key|access[_-]?token|refresh[_-]?token|"
        r"auth[_-]?token|password|secret)\b"
        r"(\s*[:=]\s*)"
        r'(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)',
        re.IGNORECASE,
    )

    KNOWN_TOKEN_PATTERN = re.compile(
        r"\b(?:"
        r"sk-[A-Za-z0-9_-]{12,}|"
        r"gh[pousr]_[A-Za-z0-9]{20,}|"
        r"github_pat_[A-Za-z0-9_]{20,}|"
        r"xox[baprs]-[A-Za-z0-9-]{10,}|"
        r"AKIA[0-9A-Z]{16}"
        r")\b"
    )

    @classmethod
    def redact(cls, text: str) -> str:
        """
        Return text with recognized sensitive patterns masked.

        Raises:
            TypeError: If the input is not a string.
        """
        if not isinstance(text, str):
            raise TypeError("PrivacyRedactor.redact() expects a string")

        # Mask bearer tokens.
        redacted = cls.BEARER_PATTERN.sub(
            "[REDACTED_TOKEN]",
            text,
        )

        # Mask values assigned to sensitive field names.
        redacted = cls.SECRET_ASSIGNMENT_PATTERN.sub(
            lambda match: (
                f"{match.group(1)}"
                f"{match.group(2)}"
                "[REDACTED_SECRET]"
            ),
            redacted,
        )

        # Mask recognizable API-key and service-token formats.
        redacted = cls.KNOWN_TOKEN_PATTERN.sub(
            "[REDACTED_TOKEN]",
            redacted,
        )

        # Mask email addresses.
        redacted = cls.EMAIL_PATTERN.sub(
            "[REDACTED_EMAIL]",
            redacted,
        )

        return redacted


def redact_sensitive_text(text: str) -> str:
    """Convenience function for redacting sensitive text."""
    return PrivacyRedactor.redact(text)