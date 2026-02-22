"""Deterministic context compaction helpers for branch execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from repoclinic.config.models import AnalysisControlsConfig
from repoclinic.schemas.scanner_models import ScannerOutput

DEPENDENCY_SEVERITY_ORDER = {
    "Critical": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
    "Unknown": 4,
}


@dataclass(frozen=True)
class CompactionStats:
    """Compaction metrics for transparency metadata."""

    original_evidence_count: int
    compacted_evidence_count: int
    original_dependency_findings: int
    compacted_dependency_findings: int


def compact_scanner_context(
    scanner_output: ScannerOutput, controls: AnalysisControlsConfig
) -> tuple[dict[str, Any], CompactionStats]:
    """Compact scanner payload deterministically using configured limits."""
    payload = scanner_output.model_dump(mode="json")
    evidence = payload.get("evidence_index", [])
    dependency_findings = payload.get("dependency_summary", {}).get(
        "vulnerability_findings", []
    )

    compacted_evidence = _select_evidence(evidence, controls)
    compacted_findings = _select_dependency_findings(dependency_findings, controls)
    compacted_tool_runs = _truncate_tool_details(payload.get("scanner_tool_runs", []))

    payload["evidence_index"] = compacted_evidence
    payload.setdefault("dependency_summary", {})["vulnerability_findings"] = (
        compacted_findings
    )
    payload["scanner_tool_runs"] = compacted_tool_runs
    payload["context_compaction"] = {
        "enabled": True,
        "original_evidence_count": len(evidence),
        "compacted_evidence_count": len(compacted_evidence),
        "original_dependency_findings": len(dependency_findings),
        "compacted_dependency_findings": len(compacted_findings),
    }

    return (
        payload,
        CompactionStats(
            original_evidence_count=len(evidence),
            compacted_evidence_count=len(compacted_evidence),
            original_dependency_findings=len(dependency_findings),
            compacted_dependency_findings=len(compacted_findings),
        ),
    )


def minimal_scanner_context(scanner_output: ScannerOutput) -> dict[str, Any]:
    """Build a minimal deterministic scanner context payload."""
    payload = scanner_output.model_dump(mode="json")
    dependency_summary = payload.get("dependency_summary", {})
    findings = dependency_summary.get("vulnerability_findings", [])
    top_findings = sorted(
        findings,
        key=lambda item: (
            DEPENDENCY_SEVERITY_ORDER.get(str(item.get("severity", "Unknown")), 99),
            str(item.get("vulnerability_id", "")),
            str(item.get("package", "")),
        ),
    )[:20]

    return {
        "schema_version": payload.get("schema_version"),
        "run_id": payload.get("run_id"),
        "repo_profile": payload.get("repo_profile"),
        "scan_stats": payload.get("scan_stats"),
        "dependency_summary": {
            "vulnerability_scan_status": dependency_summary.get(
                "vulnerability_scan_status"
            ),
            "vulnerability_findings": top_findings,
            "manifest_count": len(dependency_summary.get("manifests", [])),
        },
        "scanner_tool_runs": _truncate_tool_details(
            payload.get("scanner_tool_runs", [])
        ),
        "evidence_index": [],
        "context_compaction": {
            "enabled": True,
            "mode": "minimal",
            "note": "Context reduced to fit branch token budget.",
        },
    }


def _select_evidence(
    evidence: list[dict[str, Any]], controls: AnalysisControlsConfig
) -> list[dict[str, Any]]:
    dedup: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    for item in evidence:
        key = (
            str(item.get("file", "")),
            int(item.get("line_start", 0)),
            str(item.get("source", "")),
            str(item.get("summary", "")),
        )
        if key not in dedup:
            dedup[key] = item
    ordered = sorted(
        dedup.values(),
        key=lambda item: (
            str(item.get("source", "")),
            str(item.get("file", "")),
            int(item.get("line_start", 0)),
            int(item.get("line_end", 0)),
            str(item.get("summary", "")),
            str(item.get("id", "")),
        ),
    )
    source_counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for item in ordered:
        source = str(item.get("source", "unknown"))
        source_limit = controls.max_evidence_per_source.get(
            source, controls.max_evidence_total
        )
        if source_counts.get(source, 0) >= source_limit:
            continue
        if len(selected) >= controls.max_evidence_total:
            break
        selected.append(item)
        source_counts[source] = source_counts.get(source, 0) + 1
    return selected


def _select_dependency_findings(
    findings: list[dict[str, Any]], controls: AnalysisControlsConfig
) -> list[dict[str, Any]]:
    ordered = sorted(
        findings,
        key=lambda item: (
            DEPENDENCY_SEVERITY_ORDER.get(str(item.get("severity", "Unknown")), 99),
            str(item.get("vulnerability_id", "")),
            str(item.get("package", "")),
            str(item.get("version", "")),
        ),
    )
    return ordered[: controls.max_dependency_findings]


def _truncate_tool_details(tool_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted_runs: list[dict[str, Any]] = []
    for item in tool_runs:
        updated = dict(item)
        details = updated.get("details")
        if isinstance(details, str) and len(details) > 500:
            updated["details"] = f"{details[:497]}..."
        compacted_runs.append(updated)
    return compacted_runs
