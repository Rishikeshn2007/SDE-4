"""Generate answers grounded only in available context.

Screen content is untrusted data. Instructions found inside
screen content must never be treated as commands.
"""

import re

from schemas.context import ReasoningRequest, ReasoningResult
from observations.privacy_redactor import PrivacyRedactor


class GroundedAnswerGenerator:
    """Generate evidence-based answers with source references."""

    NO_EVIDENCE_MESSAGE = (
        "I do not have enough evidence in the provided context "
        "to answer this question."
    )

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+(all\s+)?prior\s+instructions",
        r"disregard\s+(all\s+)?instructions",
        r"override\s+(the\s+)?(system\s+)?instructions",
        r"reveal\s+(the\s+)?(system\s+)?prompt",
        r"reveal\s+confidential",
        r"act\s+as\s+(an?\s+)?(administrator|system)",
        r"bypass\s+(the\s+)?security",
    ]

    STOP_WORDS = {
        "what", "is", "are", "was", "were", "the",
        "a", "an", "in", "on", "at", "of", "to",
        "for", "does", "do", "did", "how", "when",
        "where", "who", "which", "and", "or", "it",
        "this", "that", "with", "about", "tell", "me",
        "please", "can", "could", "would", "project",
        "use", "uses", "using", "included",
    }

    PROGRAMMING_LANGUAGES = {
        "python", "java", "javascript", "typescript",
        "c", "cpp", "csharp", "ruby", "php", "go",
        "rust", "kotlin", "swift",
    }

    def _contains_injection(self, text):
        """Identify common instruction-like injection patterns."""

        normalized = " ".join(text.casefold().split())

        return any(
            re.search(pattern, normalized)
            for pattern in self.INJECTION_PATTERNS
        )

    def _normalize_word(self, word):
        """Normalize simple word variations."""

        if word.endswith("ies") and len(word) > 4:
            return word[:-3] + "y"

        if word.endswith("ing") and len(word) > 5:
            return word[:-3]

        if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
            return word[:-1]

        return word

    def _get_keywords(self, text):
        words = re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())

        return {
            self._normalize_word(word)
            for word in words
            if word not in self.STOP_WORDS
        }

    def generate(self, request):
        """Generate an answer using only matching trusted evidence."""

        if not isinstance(request, ReasoningRequest):
            raise ValueError("Invalid reasoning request")

        request.validate()

        # Redact sensitive information before processing the question.
        safe_question = PrivacyRedactor.redact(request.question)

        # Check the sanitized question for instruction injection.
        if self._contains_injection(safe_question):
            result = ReasoningResult(
                request_id=request.request_id,
                answer=self.NO_EVIDENCE_MESSAGE,
                source_ids=[],
                status="success",
            )
            result.validate()
            return result

        question_words = self._get_keywords(safe_question)

        broad_question = not question_words
        asks_about_language = "language" in question_words

        matching_items = []

        for item in request.context.items:

            # Redact sensitive information before processing context.
            safe_content = PrivacyRedactor.redact(item.content)

            # Treat screen content as untrusted data.
            if self._contains_injection(safe_content):
                continue

            content_words = self._get_keywords(safe_content)

            has_keyword_match = bool(
                question_words.intersection(content_words)
            )

            has_language_match = (
                asks_about_language
                and bool(
                    self.PROGRAMMING_LANGUAGES.intersection(content_words)
                )
            )

            if broad_question or has_keyword_match or has_language_match:
                matching_items.append((item, safe_content))

        if not matching_items:
            result = ReasoningResult(
                request_id=request.request_id,
                answer=self.NO_EVIDENCE_MESSAGE,
                source_ids=[],
                status="success",
            )
            result.validate()
            return result

        evidence = []
        source_ids = []

        for item, safe_content in matching_items:
            evidence.append(safe_content.strip())

            source_id = item.source.source_id

            if source_id not in source_ids:
                source_ids.append(source_id)

        answer = (
            "Based on the available context: "
            + " ".join(evidence)
        )

        result = ReasoningResult(
            request_id=request.request_id,
            answer=answer,
            source_ids=source_ids,
            status="success",
        )

        result.validate()
        return result