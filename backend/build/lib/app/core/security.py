from collections.abc import Mapping, Sequence
import re
from typing import Any


_SENSITIVE_MARKERS = ("api_key", "apikey", "secret", "password", "token")
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|secret)"
    r"\b\s*[:=]\s*)(?:['\"]?)([^\s,;&'\"]+)"
)
_AUTHORIZATION_HEADER = re.compile(
    r"(?i)(\bauthorization\s*[:=]\s*(?:bearer|basic)\s+)([^\s,;&]+)"
)


def _sanitize_text(value: str) -> str:
    value = _CREDENTIAL_ASSIGNMENT.sub(r"\1***REDACTED***", value)
    return _AUTHORIZATION_HEADER.sub(r"\1***REDACTED***", value)


def sanitize_for_log(value: Any) -> Any:
    """Recursively redact likely credentials before persisting structured logs."""

    if isinstance(value, Mapping):
        return {
            str(key): "***REDACTED***"
            if any(marker in str(key).lower() for marker in _SENSITIVE_MARKERS)
            else sanitize_for_log(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_for_log(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value

