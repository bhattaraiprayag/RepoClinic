"""Schema contract validation tests for phase 1."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from repoclinic.constants import SCHEMA_VERSION
from repoclinic.schemas.analysis_models import BaseFinding
from repoclinic.schemas.enums import FindingCategory, FindingStatus, ProviderType, Severity
from repoclinic.schemas.input_models import AnalyzeRequest, ProviderConfig
from repoclinic.schemas.output_models import SummaryJson


def test_invalid_severity_is_rejected() -> None:
    """Severity must use canonical enum values."""
    with pytest.raises(ValidationError):
        BaseFinding(
            id="f-1",
            category=FindingCategory.SECURITY,
            title="bad severity",
            description="bad severity",
            severity="Severe",
            status=FindingStatus.SUSPECTED,
            confidence=0.5,
            recommendation="fix",
        )


def test_confirmed_finding_requires_evidence() -> None:
    """Confirmed findings must carry evidence."""
    with pytest.raises(ValidationError):
        BaseFinding(
            id="f-2",
            category=FindingCategory.SECURITY,
            title="confirmed no evidence",
            description="missing evidence",
            severity=Severity.HIGH,
            status=FindingStatus.CONFIRMED,
            confidence=0.9,
            recommendation="fix",
            evidence=[],
        )


def test_malformed_summary_json_is_rejected() -> None:
    """summary.json contract must reject incomplete payloads."""
    with pytest.raises(ValidationError):
        SummaryJson.model_validate_json('{"schema_version":"1.0.0"}')


def test_schema_version_is_required() -> None:
    """Versioned payloads must explicitly include schema_version."""
    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate(
            {
                "input": {"source_type": "local_path", "local_path": "/tmp/repo"},
                "execution": {
                    "provider": {"type": "openai", "model": "gpt-4.1"},
                    "timeouts": {"scanner_seconds": 1, "agent_seconds": 1},
                    "feature_flags": {
                        "enable_tree_sitter": True,
                        "enable_bandit": True,
                        "enable_semgrep": True,
                        "enable_osv": True,
                    },
                },
            }
        )


def test_legacy_provider_label_maps_to_canonical_enum() -> None:
    """Legacy lmstudio labels should map to lm_studio."""
    provider = ProviderConfig(
        type="lmstudio",
        model="local-model",
        temperature=0.1,
        seed=42,
        max_tokens=2048,
    )
    assert provider.type == ProviderType.LM_STUDIO
    assert SCHEMA_VERSION == "1.0.0"
