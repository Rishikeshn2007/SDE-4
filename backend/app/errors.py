from pydantic import BaseModel
from typing import Any


class ErrorEnvelope(BaseModel):
    code: str
    message_safe_for_user: str
    retryable: bool
    correlation_id: str
    details_redacted: dict[str, Any] = {}