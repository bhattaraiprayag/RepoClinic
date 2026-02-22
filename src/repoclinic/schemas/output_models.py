"""Final output schemas for roadmap and summary artifacts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from repoclinic.schemas.base import StrictSchemaModel, VersionedRunModel
from repoclinic.schemas.enums import ArchitectureType, Priority, Severity

TimelineBucket = Literal[
    "immediate_1_2_days",
    "short_term_1_2_weeks",
    "medium_term_1_2_months",
]
StageStatus = Literal["completed", "failed", "degraded"]
ScannerStageStatus = Literal["completed", "failed"]


class RoadmapItem(StrictSchemaModel):
    """Roadmap item contract."""

    priority: Priority
    task: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    effort: str = Field(min_length=1)
    risk: str = Field(min_length=1)
    justification: str = Field(min_length=1)
    timeline_bucket: TimelineBucket
    depends_on: list[str] = Field(default_factory=list)


class SummaryRiskItem(StrictSchemaModel):
    """Flattened risk item for summary.json."""

    issue: str = Field(min_length=1)
    severity: Severity
    file: str = Field(min_length=1)


class SummaryRoadmapItem(StrictSchemaModel):
    """Minimal roadmap item for summary.json."""

    priority: Priority
    task: str = Field(min_length=1)
    effort: str = Field(min_length=1)


class AnalysisStatus(StrictSchemaModel):
    """Pipeline stage statuses."""

    scanner: ScannerStageStatus
    architecture: StageStatus
    security: StageStatus
    performance: StageStatus
    roadmap: StageStatus


class SummaryJson(VersionedRunModel):
    """Canonical summary.json schema."""

    repo_name: str = Field(min_length=1)
    language_detected: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    architecture_type: ArchitectureType
    top_security_risks: list[SummaryRiskItem] = Field(default_factory=list)
    top_performance_risks: list[SummaryRiskItem] = Field(default_factory=list)
    roadmap: list[SummaryRoadmapItem] = Field(default_factory=list)
    analysis_status: AnalysisStatus
