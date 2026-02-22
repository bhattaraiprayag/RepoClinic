"""Architecture, security, and performance output schemas."""

from __future__ import annotations

from pydantic import Field, model_validator

from repoclinic.schemas.base import StrictSchemaModel, VersionedRunModel
from repoclinic.schemas.enums import (
    ArchitectureType,
    FindingCategory,
    FindingStatus,
    Severity,
)


class FindingEvidence(StrictSchemaModel):
    """Evidence reference used by findings."""

    file: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    source: str = Field(min_length=1)
    rule_id: str | None = None


class BaseFinding(StrictSchemaModel):
    """Shared finding contract across middle branches."""

    id: str = Field(min_length=1)
    category: FindingCategory
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: Severity
    status: FindingStatus
    confidence: float = Field(ge=0.0, le=1.0)
    symptoms: list[str] = Field(default_factory=list)
    recommendation: str = Field(min_length=1)
    evidence: list[FindingEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_confirmed_has_evidence(self) -> "BaseFinding":
        if self.status == FindingStatus.CONFIRMED and not self.evidence:
            raise ValueError("confirmed findings must include evidence")
        return self


class ModuleBoundary(StrictSchemaModel):
    """Architecture module boundary."""

    name: str = Field(min_length=1)
    paths: list[str] = Field(default_factory=list)
    responsibility: str = Field(min_length=1)


class ArchitectureAgentOutput(VersionedRunModel):
    """Architecture branch output."""

    architecture_type: ArchitectureType
    module_boundaries: list[ModuleBoundary] = Field(default_factory=list)
    runtime_flow_summary: str = Field(min_length=1)
    findings: list[BaseFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_findings_category(self) -> "ArchitectureAgentOutput":
        for finding in self.findings:
            if finding.category != FindingCategory.ARCHITECTURE:
                raise ValueError(
                    "architecture output must only contain architecture findings"
                )
        return self


class SecurityRisk(StrictSchemaModel):
    """Top security risk item."""

    issue: str = Field(min_length=1)
    severity: Severity
    file: str = Field(min_length=1)


class SecurityAgentOutput(VersionedRunModel):
    """Security branch output."""

    findings: list[BaseFinding] = Field(default_factory=list)
    top_security_risks: list[SecurityRisk] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_findings_category(self) -> "SecurityAgentOutput":
        for finding in self.findings:
            if finding.category != FindingCategory.SECURITY:
                raise ValueError("security output must only contain security findings")
        return self


class PerformanceRisk(StrictSchemaModel):
    """Top performance risk item."""

    issue: str = Field(min_length=1)
    severity: Severity
    file: str = Field(min_length=1)


class PerformanceAgentOutput(VersionedRunModel):
    """Performance branch output."""

    findings: list[BaseFinding] = Field(default_factory=list)
    top_performance_risks: list[PerformanceRisk] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_findings_category(self) -> "PerformanceAgentOutput":
        for finding in self.findings:
            if finding.category != FindingCategory.PERFORMANCE:
                raise ValueError(
                    "performance output must only contain performance findings"
                )
        return self
