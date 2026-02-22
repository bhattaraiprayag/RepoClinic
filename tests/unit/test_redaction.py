"""Phase 8 redaction policy tests."""

from __future__ import annotations

from repoclinic.security.redaction import redact_mapping, redact_text


def test_redact_text_masks_api_tokens() -> None:
    """Sensitive token-like values should be masked in text."""
    text = "Authorization: Bearer sk-lm-ABCDEF1234567890 token=sk-proj-1234567890123456"
    redacted = redact_text(text)
    assert "sk-lm-ABCDEF1234567890" not in redacted
    assert "sk-proj-1234567890123456" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_mapping_masks_nested_values() -> None:
    """Redaction should traverse nested dictionaries and lists."""
    payload = {
        "api_key": "sk-test-THISISASECRET12345",
        "nested": {
            "token": "sk-lf-PRIVATESECRET",
            "values": ["safe", "Authorization: Bearer sk-lm-XYZXYZXYZXYZXYZ"],
        },
    }
    redacted = redact_mapping(payload)
    assert redacted["api_key"].endswith("[REDACTED]")
    assert redacted["nested"]["token"].endswith("[REDACTED]")
    assert "[REDACTED]" in redacted["nested"]["values"][1]
