"""
Structured Redacted Logging Module for SDE-4 Speech-to-Text Pipeline (Week 4, Day 25–27).

Security Policy:
----------------
Logs MUST NEVER contain:
- Raw audio payloads (PCM bytes, bytearrays, memoryviews)
- Encoded audio data (hex, base64 representations)
- Transcript text (spoken text, hypotheses, finalized segments)
- API keys, credentials, bearer tokens, or secrets

Logs MAY contain:
- Safe session identifiers
- Provider adapter names
- Processing durations / latencies
- Audio metadata (duration_s, sample_rate, channels, chunk count)
- Chunk sequence IDs
- Error categories, normalized codes, and recoverability flags
- Retry counts and backoff delays
- Lifecycle events (START, CHUNK, REVISION, FINAL_COMMIT, CANCEL, COMPLETE)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

# Regular expressions for detecting sensitive tokens
_CREDENTIAL_PATTERNS = [
    re.compile(r"(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}", re.IGNORECASE),
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    re.compile(r"bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?([A-Za-z0-9\-_.]+)['\"]?", re.IGNORECASE),
]

_AUDIO_BYTE_PATTERN = re.compile(
    r"b['\"][^'\"]*\\{1,2}x[0-9a-fA-F]{2}[^'\"]*['\"]",
    re.IGNORECASE,
)


class RedactedFilter(logging.Filter):
    """Logging filter that sanitizes record messages and attributes to prevent data leakage."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Sanitize message string
        if isinstance(record.msg, str):
            record.msg = self.sanitize_text(record.msg)

        # Sanitize record arguments if provided
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._sanitize_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._sanitize_value(v) for v in record.args)
            elif isinstance(record.args, list):
                record.args = [self._sanitize_value(v) for v in record.args]

        return True

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Strip raw audio representations and credentials from text."""
        if not text:
            return text

        # Redact credentials
        for pat in _CREDENTIAL_PATTERNS:
            text = pat.sub("[REDACTED_CREDENTIAL]", text)

        # Redact raw audio bytes representations
        text = _AUDIO_BYTE_PATTERN.sub("[REDACTED_AUDIO_PAYLOAD]", text)

        return text

    @classmethod
    def _sanitize_value(cls, val: Any) -> Any:
        """Sanitize individual argument values."""
        if isinstance(val, (bytes, bytearray, memoryview)):
            return f"[REDACTED_AUDIO_PAYLOAD_LEN_{len(val)}B]"
        if isinstance(val, str):
            return cls.sanitize_text(val)
        if isinstance(val, dict):
            # Check for known sensitive keys like 'text', 'transcript', 'data', 'token', 'key'
            clean = {}
            for k, v in val.items():
                k_lower = str(k).lower()
                if k_lower in ("text", "transcript", "raw_audio", "audio_data", "data", "token", "api_key", "secret"):
                    clean[k] = "[REDACTED]"
                else:
                    clean[k] = cls._sanitize_value(v)
            return clean
        return val


class RedactedFormatter(logging.Formatter):
    """Formatter that applies sanitization and formats structured metadata."""

    def __init__(
        self,
        fmt: str = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt: str = "%Y-%m-%dT%H:%M:%SZ",
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return RedactedFilter.sanitize_text(formatted)


def get_logger(name: str = "sde4_stt") -> logging.Logger:
    """Return a logger configured with redaction filter and formatter."""
    logger = logging.getLogger(name)
    # Ensure RedactedFilter is attached
    if not any(isinstance(f, RedactedFilter) for f in logger.filters):
        logger.addFilter(RedactedFilter())
    return logger


# Structured logging helper methods
def log_session_lifecycle(
    logger: logging.Logger,
    session_id: str,
    event: str,
    provider: Optional[str] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Log high-level session lifecycle events without leaking transcript or audio."""
    meta = extra_meta or {}
    logger.info(
        "Session lifecycle event: session_id=%s event=%s provider=%s metadata=%s",
        session_id,
        event,
        provider or "default",
        meta,
    )


def log_chunk_metric(
    logger: logging.Logger,
    session_id: str,
    sequence_id: int,
    duration_s: float,
    latency_ms: float,
) -> None:
    """Log chunk processing timing metadata."""
    logger.debug(
        "Processed audio chunk: session_id=%s seq=%d duration_s=%.3f latency_ms=%.2f",
        session_id,
        sequence_id,
        duration_s,
        latency_ms,
    )


def log_error_event(
    logger: logging.Logger,
    session_id: str,
    error_code: str,
    recoverable: bool,
    message: str,
) -> None:
    """Log structured error diagnostics with text redaction."""
    safe_msg = RedactedFilter.sanitize_text(message)
    logger.warning(
        "Transcription error: session_id=%s code=%s recoverable=%s reason='%s'",
        session_id,
        error_code,
        recoverable,
        safe_msg,
    )


def log_fallback_event(
    logger: logging.Logger,
    session_id: str,
    primary_provider: str,
    fallback_provider: str,
    reason: str,
) -> None:
    """Log fallback activation event."""
    safe_reason = RedactedFilter.sanitize_text(reason)
    logger.info(
        "Fallback activated: session_id=%s from=%s to=%s reason='%s'",
        session_id,
        primary_provider,
        fallback_provider,
        safe_reason,
    )
