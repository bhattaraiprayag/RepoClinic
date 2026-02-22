"""Phase 6 artifact generation tests."""

from __future__ import annotations

from pathlib import Path

from repoclinic.artifacts.generator import (
    build_report_markdown,
    build_summary_json,
    write_artifacts,
)
from repoclinic.schemas.analysis_models import (
    ArchitectureAgentOutput,
    BaseFinding,
    FindingEvidence,
    ModuleBoundary,
    PerformanceAgentOutput,
    PerformanceRisk,
    SecurityAgentOutput,
    SecurityRisk,
)
from repoclinic.schemas.enums import (
    ArchitectureType,
    FindingCategory,
    FindingStatus,
    Priority,
    Severity,
)
from repoclinic.schemas.output_models import RoadmapItem
from repoclinic.schemas.scanner_models import (
    DependencySummary,
    RepoProfile,
    ScanStats,
    ScannerOutput,
    ScannerToolRun,
)


def _scanner_output() -> ScannerOutput:
    return ScannerOutput(
        schema_version="1.0.0",
        run_id="run-artifacts",
        repo_profile=RepoProfile(
            repo_name="sample-repo",
            languages_detected=["TypeScript", "Python"],
            frameworks_detected=["FastAPI", "Express"],
            architecture_hints=["layered-service-structure"],
            entry_points=["app.py", "src/main.ts"],
            manifests=["package.json", "requirements.txt"],
        ),
        scan_stats=ScanStats(total_files_seen=12, files_scanned=10, files_skipped=2),
        dependency_summary=DependencySummary(vulnerability_scan_status="completed"),
        evidence_index=[],
        scanner_tool_runs=[
            ScannerToolRun(tool="semgrep", status="completed"),
            ScannerToolRun(
                tool="osv-scanner",
                status="unavailable",
                exit_code=128,
                details="no packages found",
            ),
        ],
    )


def _finding(
    category: FindingCategory, title: str, severity: Severity, fid: str
) -> BaseFinding:
    return BaseFinding(
        id=fid,
        category=category,
        title=title,
        description=f"{title} description",
        severity=severity,
        status=FindingStatus.CONFIRMED,
        confidence=0.8,
        symptoms=["observed symptom"],
        recommendation=f"Fix {title}",
        evidence=[
            FindingEvidence(
                file="src/app.py",
                line_start=1,
                line_end=2,
                source="semgrep",
            )
        ],
    )


def _architecture_output() -> ArchitectureAgentOutput:
    return ArchitectureAgentOutput(
        schema_version="1.0.0",
        run_id="run-artifacts",
        architecture_type=ArchitectureType.MONOLITH,
        module_boundaries=[
            ModuleBoundary(name="src", paths=["src"], responsibility="Core app logic")
        ],
        runtime_flow_summary="Runtime starts at app.py and routes through src/ modules.",
        findings=[
            _finding(
                FindingCategory.ARCHITECTURE,
                "Layered module boundaries present",
                Severity.LOW,
                "a1",
            )
        ],
    )


def _security_output() -> SecurityAgentOutput:
    return SecurityAgentOutput(
        schema_version="1.0.0",
        run_id="run-artifacts",
        findings=[
            _finding(
                FindingCategory.SECURITY,
                "Hardcoded credential risk",
                Severity.HIGH,
                "s1",
            )
        ],
        top_security_risks=[
            SecurityRisk(
                issue="Low risk item",
                severity=Severity.LOW,
                file="src/low.py",
            ),
            SecurityRisk(
                issue="High risk item",
                severity=Severity.HIGH,
                file="src/high.py",
            ),
        ],
    )


def _performance_output() -> PerformanceAgentOutput:
    return PerformanceAgentOutput(
        schema_version="1.0.0",
        run_id="run-artifacts",
        findings=[
            _finding(
                FindingCategory.PERFORMANCE,
                "Missing pagination on list endpoint",
                Severity.MEDIUM,
                "p1",
            )
        ],
        top_performance_risks=[
            PerformanceRisk(
                issue="Medium payload risk",
                severity=Severity.MEDIUM,
                file="src/routes.py",
            )
        ],
    )


def _roadmap_items() -> list[RoadmapItem]:
    return [
        RoadmapItem(
            priority=Priority.P2,
            task="Document architecture boundaries",
            impact="Improves maintainability",
            effort="Low",
            risk="Low",
            justification="Improves onboarding",
            timeline_bucket="medium_term_1_2_months",
            depends_on=["a1"],
        ),
        RoadmapItem(
            priority=Priority.P0,
            task="Rotate exposed credentials",
            impact="Prevents security compromise",
            effort="Medium",
            risk="High",
            justification="Critical security issue",
            timeline_bucket="immediate_1_2_days",
            depends_on=["s1"],
        ),
    ]


def test_summary_json_required_keys_and_sorting() -> None:
    """Summary JSON should keep required keys and deterministic ordering."""
    summary = build_summary_json(
        schema_version="1.0.0",
        run_id="run-artifacts",
        scanner_output=_scanner_output(),
        architecture_output=_architecture_output(),
        security_output=_security_output(),
        performance_output=_performance_output(),
        roadmap_items=_roadmap_items(),
        branch_statuses={
            "scanner": "completed",
            "architecture": "completed",
            "security": "completed",
            "performance": "completed",
            "roadmap": "completed",
        },
    )
    payload = summary.model_dump(mode="json")
    assert set(payload.keys()) == {
        "schema_version",
        "run_id",
        "repo_name",
        "language_detected",
        "frameworks",
        "architecture_type",
        "top_security_risks",
        "top_performance_risks",
        "roadmap",
        "scanner_tooling",
        "analysis_status",
    }
    assert payload["top_security_risks"][0]["severity"] == "High"
    assert payload["roadmap"][0]["priority"] == "P0"
    assert any(
        item["status"] == "tooling_unavailable" for item in payload["scanner_tooling"]
    )


def test_report_section_order_is_fixed() -> None:
    """Report markdown should follow fixed required section ordering."""
    report = build_report_markdown(
        scanner_output=_scanner_output(),
        architecture_output=_architecture_output(),
        security_output=_security_output(),
        performance_output=_performance_output(),
        roadmap_items=_roadmap_items(),
    )
    sections = [
        "## Repository Overview",
        "## Architecture Summary",
        "## Key Components / Modules",
        "## Security Risks",
        "## Performance & Scalability Risks",
        "## Roadmap / Improvement Plan",
        "## Summary Table (Top 10 issues)",
    ]
    indices = [report.index(section) for section in sections]
    assert indices == sorted(indices)


def test_degraded_status_propagates_to_summary() -> None:
    """Degraded and failed branch statuses must be reflected in summary."""
    summary = build_summary_json(
        schema_version="1.0.0",
        run_id="run-artifacts",
        scanner_output=_scanner_output(),
        architecture_output=_architecture_output(),
        security_output=_security_output(),
        performance_output=_performance_output(),
        roadmap_items=_roadmap_items(),
        branch_statuses={
            "scanner": "completed",
            "architecture": "completed",
            "security": "failed",
            "performance": "completed",
            "roadmap": "degraded",
        },
    )
    assert summary.analysis_status.security == "failed"
    assert summary.analysis_status.roadmap == "degraded"


def test_write_artifacts_creates_output_files(tmp_path: Path) -> None:
    """Artifact writer should persist summary.json and report.md."""
    summary = build_summary_json(
        schema_version="1.0.0",
        run_id="run-artifacts",
        scanner_output=_scanner_output(),
        architecture_output=_architecture_output(),
        security_output=_security_output(),
        performance_output=_performance_output(),
        roadmap_items=_roadmap_items(),
        branch_statuses={
            "scanner": "completed",
            "architecture": "completed",
            "security": "completed",
            "performance": "completed",
            "roadmap": "completed",
        },
    )
    report = build_report_markdown(
        scanner_output=_scanner_output(),
        architecture_output=_architecture_output(),
        security_output=_security_output(),
        performance_output=_performance_output(),
        roadmap_items=_roadmap_items(),
    )
    generated = write_artifacts(
        output_dir=tmp_path, summary=summary, report_markdown=report
    )
    assert generated.summary_path.exists()
    assert generated.report_path.exists()
    assert generated.summary_path.read_text(encoding="utf-8").strip().startswith("{")
