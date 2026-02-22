"""Normalization of scanner/tool outputs into canonical schema objects."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from repoclinic.schemas.scanner_models import (
    DependencySeverity,
    DependencyFinding,
    EvidenceItem,
    ScannerEvidenceSource,
    ScannerSignalType,
)


def build_heuristic_evidence(
    *,
    entry_points: list[str],
    manifests: list[str],
) -> list[EvidenceItem]:
    """Build heuristic evidence for entrypoints and manifests."""
    evidence: list[EvidenceItem] = []
    for entry in entry_points:
        evidence.append(
            _make_evidence(
                file=entry,
                line_start=1,
                line_end=1,
                source="scanner_heuristic",
                signal_type="entrypoint",
                summary=f"Entrypoint candidate: {entry}",
                confidence=0.75,
            )
        )
    for manifest in manifests:
        evidence.append(
            _make_evidence(
                file=manifest,
                line_start=1,
                line_end=1,
                source="scanner_heuristic",
                signal_type="dependency",
                summary=f"Dependency manifest detected: {manifest}",
                confidence=0.7,
            )
        )
    return evidence


def normalize_semgrep(payload: dict[str, Any]) -> list[EvidenceItem]:
    """Normalize Semgrep JSON into evidence items."""
    evidence: list[EvidenceItem] = []
    for item in payload.get("results", []):
        file = item.get("path")
        if not file:
            continue
        start_line = int(item.get("start", {}).get("line", 1))
        end_line = int(item.get("end", {}).get("line", start_line))
        message = item.get("extra", {}).get("message") or item.get(
            "check_id", "Semgrep finding"
        )
        evidence.append(
            _make_evidence(
                file=file,
                line_start=start_line,
                line_end=end_line,
                source="semgrep",
                signal_type="vuln",
                summary=message,
                confidence=0.9,
            )
        )
    return evidence


def normalize_bandit(payload: dict[str, Any]) -> list[EvidenceItem]:
    """Normalize Bandit JSON into evidence items."""
    evidence: list[EvidenceItem] = []
    for item in payload.get("results", []):
        file = item.get("filename")
        if not file:
            continue
        line = int(item.get("line_number", 1))
        summary = item.get("issue_text") or item.get("test_name") or "Bandit finding"
        evidence.append(
            _make_evidence(
                file=str(Path(file)),
                line_start=line,
                line_end=line,
                source="bandit",
                signal_type="vuln",
                summary=summary,
                confidence=0.85,
            )
        )
    return evidence


def normalize_osv(
    payload: dict[str, Any],
) -> tuple[list[EvidenceItem], list[DependencyFinding]]:
    """Normalize OSV JSON into evidence items and dependency findings."""
    evidence: list[EvidenceItem] = []
    dependency_findings: list[DependencyFinding] = []
    for result in payload.get("results", []):
        source_file = result.get("source", {}).get("path", "unknown")
        for package in result.get("packages", []):
            package_name = package.get("package", {}).get("name")
            ecosystem = package.get("package", {}).get("ecosystem", "unknown")
            version = package.get("package", {}).get("version", "unknown")
            for vuln in package.get("vulnerabilities", []):
                vuln_id = vuln.get("id", "unknown")
                aliases = vuln.get("aliases", [])
                severity = _normalize_dependency_severity(
                    vuln.get("database_specific", {}).get("severity")
                )
                fixed_version = None
                if vuln.get("affected"):
                    ranges = vuln["affected"][0].get("ranges", [])
                    if ranges and ranges[0].get("events"):
                        for event in ranges[0]["events"]:
                            if "fixed" in event:
                                fixed_version = event["fixed"]
                                break

                if package_name:
                    dependency_findings.append(
                        DependencyFinding(
                            package=package_name,
                            ecosystem=ecosystem,
                            version=version,
                            vulnerability_id=vuln_id,
                            aliases=aliases,
                            severity=severity,
                            fixed_version=fixed_version,
                            source_file=source_file,
                        )
                    )
                    evidence.append(
                        _make_evidence(
                            file=source_file,
                            line_start=1,
                            line_end=1,
                            source="osv",
                            signal_type="dependency",
                            summary=f"{package_name} vulnerable to {vuln_id}",
                            confidence=0.9,
                        )
                    )
    return evidence, dependency_findings


def _normalize_dependency_severity(raw: Any) -> DependencySeverity:
    severity_map: dict[str, DependencySeverity] = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "critical": "Critical",
    }
    if not raw:
        return "Unknown"
    normalized = severity_map.get(str(raw).strip().lower())
    return normalized or "Unknown"


def _make_evidence(
    *,
    file: str,
    line_start: int,
    line_end: int,
    source: ScannerEvidenceSource,
    signal_type: ScannerSignalType,
    summary: str,
    confidence: float,
) -> EvidenceItem:
    basis = f"{file}:{line_start}:{line_end}:{source}:{signal_type}:{summary}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return EvidenceItem(
        id=digest[:16],
        file=file,
        line_start=line_start,
        line_end=line_end,
        snippet_hash=digest,
        source=source,
        signal_type=signal_type,
        summary=summary,
        confidence=confidence,
    )
