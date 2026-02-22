"""Phase 6 artifact assembly and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import orjson

from repoclinic.schemas.analysis_models import (
    ArchitectureAgentOutput,
    BaseFinding,
    PerformanceAgentOutput,
    SecurityAgentOutput,
)
from repoclinic.schemas.enums import FindingStatus, Priority, Severity
from repoclinic.schemas.output_models import (
    AnalysisStatus,
    RoadmapItem,
    SummaryJson,
    SummaryRiskItem,
    SummaryRoadmapItem,
)
from repoclinic.schemas.scanner_models import ScannerOutput

SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}
PRIORITY_ORDER = {
    Priority.P0: 0,
    Priority.P1: 1,
    Priority.P2: 2,
}


@dataclass(frozen=True)
class GeneratedArtifacts:
    """Generated artifact payload."""

    summary: SummaryJson
    report_markdown: str
    summary_path: Path
    report_path: Path


def build_summary_json(
    *,
    schema_version: str,
    run_id: str,
    scanner_output: ScannerOutput,
    architecture_output: ArchitectureAgentOutput,
    security_output: SecurityAgentOutput,
    performance_output: PerformanceAgentOutput,
    roadmap_items: list[RoadmapItem],
    branch_statuses: dict[str, str],
) -> SummaryJson:
    """Assemble and validate summary.json payload."""
    top_security_risks = sorted(
        [
            SummaryRiskItem(
                issue=risk.issue,
                severity=risk.severity,
                file=risk.file,
            )
            for risk in security_output.top_security_risks
        ],
        key=lambda risk: (SEVERITY_ORDER[risk.severity], risk.issue, risk.file),
    )
    top_performance_risks = sorted(
        [
            SummaryRiskItem(
                issue=risk.issue,
                severity=risk.severity,
                file=risk.file,
            )
            for risk in performance_output.top_performance_risks
        ],
        key=lambda risk: (SEVERITY_ORDER[risk.severity], risk.issue, risk.file),
    )
    roadmap = sorted(
        [
            SummaryRoadmapItem(
                priority=item.priority,
                task=item.task,
                effort=item.effort,
            )
            for item in roadmap_items
        ],
        key=lambda item: (PRIORITY_ORDER[item.priority], item.task),
    )

    return SummaryJson(
        schema_version=schema_version,
        run_id=run_id,
        repo_name=scanner_output.repo_profile.repo_name,
        language_detected=sorted(scanner_output.repo_profile.languages_detected),
        frameworks=sorted(scanner_output.repo_profile.frameworks_detected),
        architecture_type=architecture_output.architecture_type,
        top_security_risks=top_security_risks[:5],
        top_performance_risks=top_performance_risks[:5],
        roadmap=roadmap,
        analysis_status=AnalysisStatus(
            scanner=_normalize_scanner_status(branch_statuses.get("scanner")),
            architecture=_normalize_stage_status(branch_statuses.get("architecture")),
            security=_normalize_stage_status(branch_statuses.get("security")),
            performance=_normalize_stage_status(branch_statuses.get("performance")),
            roadmap=_normalize_stage_status(branch_statuses.get("roadmap")),
        ),
    )


def build_report_markdown(
    *,
    scanner_output: ScannerOutput,
    architecture_output: ArchitectureAgentOutput,
    security_output: SecurityAgentOutput,
    performance_output: PerformanceAgentOutput,
    roadmap_items: list[RoadmapItem],
) -> str:
    """Render report.md using fixed section ordering."""
    combined_findings = _top_findings(
        architecture_output.findings
        + security_output.findings
        + performance_output.findings
    )
    summary_table_rows = "\n".join(
        [
            f"| {idx} | {finding.category.value} | {finding.severity.value} | {finding.title} | {finding.status.value} |"
            for idx, finding in enumerate(combined_findings[:10], start=1)
        ]
    )
    if not summary_table_rows:
        summary_table_rows = "| 1 | architecture | Low | No actionable findings | insufficient_evidence |"

    security_lines = _finding_lines(security_output.findings)
    performance_lines = _finding_lines(performance_output.findings)
    roadmap_lines = _roadmap_lines(roadmap_items)
    module_lines = (
        "\n".join(
            [
                f"- **{module.name}**: {module.responsibility} (`{', '.join(module.paths)}`)"
                for module in architecture_output.module_boundaries
            ]
        )
        or "- No module boundaries detected."
    )
    entry_points = ", ".join(scanner_output.repo_profile.entry_points) or "Not detected"
    manifests = ", ".join(scanner_output.repo_profile.manifests) or "Not detected"

    return "\n".join(
        [
            "# Repository Analysis Report",
            "",
            "## Repository Overview",
            f"- Repository: `{scanner_output.repo_profile.repo_name}`",
            f"- Languages detected: {', '.join(scanner_output.repo_profile.languages_detected) or 'Unknown'}",
            f"- Frameworks detected: {', '.join(scanner_output.repo_profile.frameworks_detected) or 'Unknown'}",
            f"- Entry points: {entry_points}",
            f"- Dependency manifests: {manifests}",
            f"- Files scanned: {scanner_output.scan_stats.files_scanned}",
            f"- Files skipped: {scanner_output.scan_stats.files_skipped}",
            "",
            "## Architecture Summary",
            f"- Architecture type: `{architecture_output.architecture_type.value}`",
            f"- Runtime flow: {architecture_output.runtime_flow_summary}",
            "",
            "## Key Components / Modules",
            module_lines,
            "",
            "## Security Risks",
            security_lines,
            "",
            "## Performance & Scalability Risks",
            performance_lines,
            "",
            "## Roadmap / Improvement Plan",
            roadmap_lines,
            "",
            "## Summary Table (Top 10 issues)",
            "| # | Category | Severity | Issue | Status |",
            "|---|---|---|---|---|",
            summary_table_rows,
            "",
        ]
    )


def write_artifacts(
    *,
    output_dir: Path,
    summary: SummaryJson,
    report_markdown: str,
) -> GeneratedArtifacts:
    """Write summary.json and report.md to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "report.md"

    summary_bytes = orjson.dumps(summary.model_dump(mode="json"), option=orjson.OPT_INDENT_2)
    summary_path.write_bytes(summary_bytes + b"\n")
    report_path.write_text(report_markdown, encoding="utf-8")

    return GeneratedArtifacts(
        summary=summary,
        report_markdown=report_markdown,
        summary_path=summary_path,
        report_path=report_path,
    )


def _normalize_stage_status(value: str | None) -> str:
    if value in {"completed", "failed", "degraded"}:
        return value
    return "failed"


def _normalize_scanner_status(value: str | None) -> str:
    if value in {"completed", "failed"}:
        return value
    return "failed"


def _top_findings(findings: list[BaseFinding]) -> list[BaseFinding]:
    actionable = [
        finding
        for finding in findings
        if finding.status
        not in {FindingStatus.NOT_APPLICABLE, FindingStatus.INSUFFICIENT_EVIDENCE}
    ]
    return sorted(
        actionable,
        key=lambda finding: (
            SEVERITY_ORDER.get(finding.severity, 4),
            1 - finding.confidence,
            finding.title,
        ),
    )


def _finding_lines(findings: list[BaseFinding]) -> str:
    if not findings:
        return "- No findings."
    lines = []
    for finding in _top_findings(findings):
        lines.append(
            f"- **{finding.severity.value}** `{finding.status.value}` - {finding.title}: {finding.recommendation}"
        )
    return "\n".join(lines)


def _roadmap_lines(items: list[RoadmapItem]) -> str:
    if not items:
        return "- No roadmap items generated."
    ordered = sorted(items, key=lambda item: (PRIORITY_ORDER[item.priority], item.task))
    return "\n".join(
        [
            (
                f"- **{item.priority.value}** ({item.timeline_bucket}) - {item.task} "
                f"[impact: {item.impact}; effort: {item.effort}; risk: {item.risk}]"
            )
            for item in ordered
        ]
    )
