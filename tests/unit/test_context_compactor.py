"""Context compaction behavior tests."""

from __future__ import annotations

from repoclinic.agents.context_compactor import (
    compact_scanner_context,
    minimal_scanner_context,
)
from repoclinic.config.models import AnalysisControlsConfig
from repoclinic.schemas.scanner_models import (
    DependencyFinding,
    DependencySummary,
    EvidenceItem,
    RepoProfile,
    ScanStats,
    ScannerOutput,
)


def _scanner_output() -> ScannerOutput:
    evidence = [
        EvidenceItem(
            id=f"e-{idx}",
            file=f"src/file_{idx % 3}.py",
            line_start=(idx % 50) + 1,
            line_end=(idx % 50) + 1,
            snippet_hash=f"hash-{idx}",
            source="bandit" if idx % 2 == 0 else "semgrep",
            signal_type="vuln",
            summary=f"finding-{idx % 7}",
            confidence=0.8,
        )
        for idx in range(120)
    ]
    findings = [
        DependencyFinding(
            package=f"pkg-{idx}",
            ecosystem="PyPI",
            version="1.0.0",
            vulnerability_id=f"GHSA-{idx}",
            aliases=[],
            severity="High" if idx % 3 == 0 else "Medium",
            source_file="requirements.txt",
        )
        for idx in range(90)
    ]
    return ScannerOutput(
        schema_version="1.0.0",
        run_id="run-compaction",
        repo_profile=RepoProfile(
            repo_name="repo",
            languages_detected=["Python"],
            frameworks_detected=[],
            architecture_hints=[],
            entry_points=["main.py"],
            manifests=["requirements.txt"],
        ),
        scan_stats=ScanStats(total_files_seen=150, files_scanned=120, files_skipped=30),
        dependency_summary=DependencySummary(
            manifests=[],
            vulnerability_scan_status="completed",
            vulnerability_findings=findings,
        ),
        evidence_index=evidence,
        scanner_tool_runs=[],
    )


def test_compaction_limits_evidence_and_dependency_counts() -> None:
    """Compaction should enforce configured count caps deterministically."""
    scanner_output = _scanner_output()
    controls = AnalysisControlsConfig(
        max_evidence_total=40,
        max_evidence_per_source={"bandit": 20, "semgrep": 20},
        max_dependency_findings=25,
    )

    compacted_payload, stats = compact_scanner_context(scanner_output, controls)

    assert stats.original_evidence_count == 120
    assert stats.compacted_evidence_count <= 40
    assert stats.compacted_dependency_findings <= 25
    evidence = compacted_payload["evidence_index"]
    assert evidence == sorted(
        evidence,
        key=lambda item: (
            item["source"],
            item["file"],
            item["line_start"],
            item["line_end"],
            item["summary"],
            item["id"],
        ),
    )


def test_minimal_context_drops_verbose_evidence() -> None:
    """Minimal fallback context should keep structural metadata and drop evidence."""
    payload = minimal_scanner_context(_scanner_output())

    assert payload["repo_profile"]["repo_name"] == "repo"
    assert payload["scan_stats"]["files_scanned"] == 120
    assert payload["evidence_index"] == []
    assert payload["context_compaction"]["mode"] == "minimal"
