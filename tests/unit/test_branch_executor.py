"""Phase 5 branch analyzer tests."""

from __future__ import annotations

from repoclinic.agents.executor import HeuristicBranchExecutor
from repoclinic.schemas.analysis_models import BaseFinding
from repoclinic.schemas.enums import FindingStatus
from repoclinic.schemas.scanner_models import (
    DependencySummary,
    EvidenceItem,
    RepoProfile,
    ScanStats,
    ScannerOutput,
)


def _scanner_output() -> ScannerOutput:
    return ScannerOutput(
        schema_version="1.0.0",
        run_id="run-branch-test",
        repo_profile=RepoProfile(
            repo_name="sample_repo",
            languages_detected=["Python", "JavaScript"],
            frameworks_detected=["FastAPI", "Express"],
            architecture_hints=[
                "layered-service-structure",
                "route-controller-pattern",
            ],
            entry_points=["app.py"],
            manifests=["package.json", "requirements.txt"],
        ),
        scan_stats=ScanStats(),
        dependency_summary=DependencySummary(vulnerability_scan_status="completed"),
        evidence_index=[
            EvidenceItem(
                id="e1",
                file="app.py",
                line_start=1,
                line_end=5,
                snippet_hash="hash1",
                source="scanner_heuristic",
                signal_type="entrypoint",
                summary="Entrypoint candidate: app.py",
                confidence=0.8,
            ),
            EvidenceItem(
                id="e2",
                file="config.py",
                line_start=10,
                line_end=12,
                snippet_hash="hash2",
                source="semgrep",
                signal_type="vuln",
                summary="Hardcoded secret-like token",
                confidence=0.9,
            ),
            EvidenceItem(
                id="e3",
                file="routes/users.js",
                line_start=8,
                line_end=18,
                snippet_hash="hash3",
                source="scanner_heuristic",
                signal_type="route",
                summary="List endpoint without explicit pagination",
                confidence=0.65,
            ),
        ],
    )


def _confirmed_findings_have_evidence(findings: list[BaseFinding]) -> bool:
    for finding in findings:
        if finding.status == FindingStatus.CONFIRMED and not finding.evidence:
            return False
    return True


def test_heuristic_branch_outputs_are_schema_valid() -> None:
    """Architecture/security/performance outputs should be schema-valid and evidence-linked."""
    executor = HeuristicBranchExecutor()
    scanner_output = _scanner_output()

    architecture = executor.run_architecture(scanner_output)
    security = executor.run_security(scanner_output)
    performance = executor.run_performance(scanner_output)

    assert architecture.findings
    assert security.findings
    assert performance.findings
    assert _confirmed_findings_have_evidence(architecture.findings)
    assert _confirmed_findings_have_evidence(security.findings)
    assert _confirmed_findings_have_evidence(performance.findings)
    security_titles = {finding.title for finding in security.findings}
    assert "Hardcoded secrets review" in security_titles
    assert "Input validation coverage review" in security_titles
    assert "Dependency vulnerability review" in security_titles
    performance_titles = {finding.title for finding in performance.findings}
    assert "N+1 query pattern review" in performance_titles
    assert "API pagination review" in performance_titles
    assert "Loop and file I/O hotspot review" in performance_titles


def test_roadmap_synthesis_prioritizes_actionable_findings() -> None:
    """Roadmap synthesis should produce non-empty actionable items from branch findings."""
    executor = HeuristicBranchExecutor()
    scanner_output = _scanner_output()
    architecture = executor.run_architecture(scanner_output)
    security = executor.run_security(scanner_output)
    performance = executor.run_performance(scanner_output)

    roadmap = executor.run_roadmap(
        architecture_output=architecture,
        security_output=security,
        performance_output=performance,
    )
    assert roadmap
    assert all(item.depends_on for item in roadmap)
