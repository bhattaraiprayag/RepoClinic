"""Redaction utilities for sensitive text and payloads."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"
SENSITIVE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9:_-]{16,}\b"),
    re.compile(r"\bpk-lf-[A-Za-z0-9:_-]{8,}\b"),
    re.compile(r"\bsk-lf-[A-Za-z0-9:_-]{8,}\b"),
    re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)[A-Za-z0-9._:-]+\b"),
    re.compile(r"(?i)\b(api[-_ ]?key\s*[=:]\s*)[\"']?[A-Za-z0-9._:-]{8,}[\"']?"),
    re.compile(r"(?i)\b(token\s*[=:]\s*)[\"']?[A-Za-z0-9._:-]{8,}[\"']?"),
]


def redact_text(value: str) -> str:
    """Redact secrets from a text value."""
    redacted = value
    for pattern in SENSITIVE_PATTERNS:
        if pattern.pattern.startswith("(?i)\\b(authorization"):
            redacted = pattern.sub(r"\1" + REDACTED, redacted)
        elif pattern.pattern.startswith("(?i)\\b(api") or pattern.pattern.startswith(
            "(?i)\\b(token"
        ):
            redacted = pattern.sub(r"\1" + REDACTED, redacted)
        else:
            redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact_mapping(value: Any) -> Any:
    """Recursively redact strings in nested dictionaries/lists."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_mapping(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    return value
