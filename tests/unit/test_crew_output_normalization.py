"""Crew output normalization tests."""

from __future__ import annotations

from pydantic import ValidationError

from repoclinic.agents.executor import (
    _is_schema_validation_error,
    _normalize_output_payload,
    _validate_output_model_payload,
)
from repoclinic.schemas.analysis_models import ArchitectureAgentOutput


def test_normalize_output_payload_coerces_unknown_severity() -> None:
    """Unknown severity values should be coerced to schema-safe defaults."""
    payload = {"findings": [{"severity": "Unknown"}]}
    normalized = _normalize_output_payload(payload)
    assert normalized["findings"][0]["severity"] == "Medium"


def test_validate_output_payload_accepts_unknown_severity_via_normalization() -> None:
    """Validation helper should recover from LM-style unknown severities."""
    payload = {
        "schema_version": "1.0.0",
        "run_id": "run-test",
        "architecture_type": "monolith",
        "runtime_flow_summary": "Runtime starts from main.py",
        "findings": [
            {
                "id": "finding-1",
                "category": "security",
                "title": "Architecture finding",
                "description": "Generated finding",
                "severity": "Unknown",
                "status": "unknown",
                "confidence": 1.7,
                "symptoms": [],
                "recommendation": "Review finding details",
                "evidence": [
                    {"file": "", "line_start": 0, "line_end": "0", "source": "model"}
                ],
            }
        ],
    }

    output = _validate_output_model_payload(payload, ArchitectureAgentOutput)
    assert output.findings[0].severity.value == "Medium"
    assert output.findings[0].category.value == "architecture"
    assert output.findings[0].status.value == "suspected"
    assert output.findings[0].confidence == 1.0
    assert output.findings[0].evidence[0].file == "N/A"
    assert output.findings[0].evidence[0].line_start == 1
    assert output.findings[0].evidence[0].line_end == 1


def test_schema_validation_error_detector_handles_pydantic_errors() -> None:
    """Schema validation detector should recognize pydantic validation exceptions."""
    try:
        ArchitectureAgentOutput.model_validate({})
    except ValidationError as exc:
        assert _is_schema_validation_error(exc)
