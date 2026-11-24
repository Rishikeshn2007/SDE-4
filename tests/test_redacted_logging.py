"""
Security and Redacted Logging Tests (Week 4, Day 25–27).

Verifies that no transcript text, raw audio bytes, encoded audio payloads,
or credentials ever leak into logs at any level (DEBUG, INFO, WARNING, ERROR).
"""

from __future__ import annotations

import io
import logging
from typing import List

from academia_audio.schemas import AudioChunk, AudioFormat
from sde4_stt.adapters.fake_transcriber import FakeTranscriber
from sde4_stt.logging import (
    RedactedFilter,
    RedactedFormatter,
    get_logger,
    log_chunk_metric,
    log_error_event,
    log_fallback_event,
    log_session_lifecycle,
)
from sde4_stt.orchestrator import TranscriptionOrchestrator


def _capture_logger_output(logger_name: str) -> tuple[logging.Logger, io.StringIO, logging.Handler]:
    """Attach a memory stream handler with RedactedFormatter to the named logger."""
    logger = get_logger(logger_name)
    logger.setLevel(logging.DEBUG)
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(RedactedFormatter())
    logger.addHandler(handler)
    return logger, log_stream, handler


def test_redacted_filter_sanitizes_credentials():
    """Verify API keys and credentials are systematically redacted."""
    sensitive_samples = [
        "Connecting with token gho_1234567890abcdefghijklmnopqrstuvwxyz",
        "Using Google API key AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q",
        "Authorization: Bearer my_secret_oauth_token_12345",
        "Failed request: api_key='sk_live_secret_key_999'",
    ]

    for sample in sensitive_samples:
        clean = RedactedFilter.sanitize_text(sample)
        assert "gho_" not in clean
        assert "AIzaSy" not in clean
        assert "my_secret_oauth" not in clean
        assert "sk_live" not in clean
        assert "[REDACTED_CREDENTIAL]" in clean


def test_redacted_filter_sanitizes_raw_audio_bytes():
    """Verify raw byte strings and byte objects are not dumped in plain text."""
    # Byte argument
    raw_pcm = b"\x00\x10\x20\x30\x40\x50\x60\x70" * 20
    arg_clean = RedactedFilter._sanitize_value(raw_pcm)
    assert "[REDACTED_AUDIO_PAYLOAD" in arg_clean
    assert "\x10\x20" not in arg_clean

    # In-text byte representation
    text_with_bytes = f"Raw buffer received: {b'\\x01\\x02\\x03\\x04\\x05'}"
    text_clean = RedactedFilter.sanitize_text(text_with_bytes)
    assert "[REDACTED_AUDIO_PAYLOAD]" in text_clean


def test_redacted_filter_sanitizes_sensitive_dictionary_keys():
    """Verify dictionary payloads with transcript or text keys are redacted."""
    data = {
        "session_id": "sess_123",
        "text": "Secret patient diagnosis: hypertension and diabetes",
        "transcript": "Secret student exam score was 95%",
        "status": "success",
    }
    cleaned = RedactedFilter._sanitize_value(data)
    assert cleaned["session_id"] == "sess_123"
    assert cleaned["text"] == "[REDACTED]"
    assert cleaned["transcript"] == "[REDACTED]"
    assert cleaned["status"] == "success"
    assert "hypertension" not in str(cleaned)
    assert "exam score" not in str(cleaned)


def test_orchestrator_execution_does_not_leak_transcript_or_audio_to_logs():
    """Run an end-to-end transcription with synthetic secret text and verify zero log leakage."""
    logger_name = "sde4_stt.orchestrator"
    logger, stream, handler = _capture_logger_output(logger_name)

    secret_phrase = "TOP_SECRET_RESEARCH_PROJECT_OMEGA_42"
    secret_bytes = b"\x7f\x80\x81\x82" * 500  # distinct identifiable byte pattern

    try:
        fmt = AudioFormat(sample_rate=16000, channels=1)
        chunk = AudioChunk(sequence_id=0, timestamp_s=0.0, format=fmt, data=secret_bytes)

        adapter = FakeTranscriber(canned_transcript=secret_phrase)
        orch = TranscriptionOrchestrator(adapter=adapter)

        result = orch.transcribe([chunk], session_id="test_security_session")
        assert result.full_text == secret_phrase

        log_content = stream.getvalue()

        # Assert no leak of secret text
        assert secret_phrase not in log_content
        assert "OMEGA_42" not in log_content
        assert "RESEARCH_PROJECT" not in log_content

        # Assert no leak of raw audio bytes
        assert "\\x7f\\x80\\x81\\x82" not in log_content
        assert str(secret_bytes) not in log_content

        # Assert safe metadata is present
        assert "test_security_session" in log_content
    finally:
        logger.removeHandler(handler)


def test_helper_loggers_structure_without_leaks():
    """Verify structured logging helper functions don't leak secrets."""
    logger_name = "sde4_stt.test_helpers"
    logger, stream, handler = _capture_logger_output(logger_name)

    try:
        log_session_lifecycle(logger, "sess_abc", "START", "mock-transcriber", {"chunks": 5})
        log_chunk_metric(logger, "sess_abc", 1, 0.25, 4.5)
        log_error_event(logger, "sess_abc", "ERR_CODE", False, "Failed with token gho_secrettoken1234567890")
        log_fallback_event(logger, "sess_abc", "primary_stt", "mock_stt", "network error with key AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q")

        output = stream.getvalue()

        assert "sess_abc" in output
        assert "START" in output
        assert "ERR_CODE" in output
        assert "primary_stt" in output
        assert "mock_stt" in output

        # Credentials must be stripped
        assert "gho_secrettoken" not in output
        assert "AIzaSy" not in output
        assert "[REDACTED_CREDENTIAL]" in output
    finally:
        logger.removeHandler(handler)
