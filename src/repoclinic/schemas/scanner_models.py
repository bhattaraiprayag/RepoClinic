"""Scanner-stage schema contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from repoclinic.schemas.base import StrictSchemaModel, VersionedRunModel

DependencySeverity = Literal["Low", "Medium", "High", "Critical", "Unknown"]
ScannerSignalType = Literal[
    "entrypoint",
    "config",
    "route",
    "auth",
    "db",
    "perf_hotspot",
    "secret",
    "vuln",
    "dependency",
]
ScannerEvidenceSource = Literal[
    "rg",
    "semgrep",
    "bandit",
    "osv",
    "tree_sitter",
    "scanner_heuristic",
]
ToolExecutionStatus = Literal["completed", "failed", "unavailable"]


class SkipReasons(StrictSchemaModel):
    """Reasons for file scan skips."""

    ignored_pathspec: int = 0
    binary: int = 0
    too_large: int = 0
    encoding_error: int = 0


class ScanStats(StrictSchemaModel):
    """Scan statistics for repository traversal."""

    total_files_seen: int = 0
    files_scanned: int = 0
    files_skipped: int = 0
    skipped_reasons: SkipReasons = Field(default_factory=SkipReasons)


class FolderSummary(StrictSchemaModel):
    """Detected top-level folder purpose."""

    path: str = Field(min_length=1)
    purpose_guess: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class EvidenceItem(StrictSchemaModel):
    """Atomic evidence item used by downstream agents."""

    id: str = Field(min_length=1)
    file: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    snippet_hash: str = Field(min_length=1)
    source: ScannerEvidenceSource
    signal_type: ScannerSignalType
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class DependencyFinding(StrictSchemaModel):
    """Dependency vulnerability finding."""

    package: str = Field(min_length=1)
    ecosystem: str = Field(min_length=1)
    version: str = Field(min_length=1)
    vulnerability_id: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    severity: DependencySeverity
    fixed_version: str | None = None
    source_file: str = Field(min_length=1)


class ManifestSummary(StrictSchemaModel):
    """Summary of a dependency manifest."""

    path: str = Field(min_length=1)
    ecosystem: str = Field(min_length=1)
    direct_dependency_count: int = Field(ge=0)


class DependencySummary(StrictSchemaModel):
    """Dependency summary plus scan status."""

    manifests: list[ManifestSummary] = Field(default_factory=list)
    vulnerability_scan_status: Literal["completed", "failed", "unavailable"] = (
        "unavailable"
    )
    vulnerability_findings: list[DependencyFinding] = Field(default_factory=list)


class ScannerToolRun(StrictSchemaModel):
    """Execution status for an external scanner tool."""

    tool: str = Field(min_length=1)
    status: ToolExecutionStatus
    exit_code: int | None = None
    details: str | None = None


class RepoProfile(StrictSchemaModel):
    """High-level repository profile discovered by scanner."""

    repo_name: str = Field(min_length=1)
    languages_detected: list[str] = Field(default_factory=list)
    frameworks_detected: list[str] = Field(default_factory=list)
    architecture_hints: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    manifests: list[str] = Field(default_factory=list)


class ScannerOutput(VersionedRunModel):
    """Scanner output consumed by all middle branches."""

    repo_profile: RepoProfile
    scan_stats: ScanStats
    folders: list[FolderSummary] = Field(default_factory=list)
    dependency_summary: DependencySummary = Field(default_factory=DependencySummary)
    evidence_index: list[EvidenceItem] = Field(default_factory=list)
    scanner_tool_runs: list[ScannerToolRun] = Field(default_factory=list)
