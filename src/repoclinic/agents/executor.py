"""Branch executor implementations for phase 5."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Protocol, TypeVar

import orjson
from crewai import Agent, Crew, Process, Task
from pydantic import BaseModel

from repoclinic.config.model_factory import ModelFactory
from repoclinic.config.models import AppConfig
from repoclinic.config.token_budget import TokenBudgeter
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
from repoclinic.schemas.enums import ArchitectureType, FindingCategory, FindingStatus, Severity
from repoclinic.schemas.output_models import RoadmapItem
from repoclinic.schemas.scanner_models import EvidenceItem, ScannerOutput

MODEL_T = TypeVar("MODEL_T", bound=BaseModel)

SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


class BranchExecutor(Protocol):
    """Branch execution contract."""

    def run_architecture(self, scanner_output: ScannerOutput) -> ArchitectureAgentOutput:
        """Run architecture branch analysis."""

    def run_security(self, scanner_output: ScannerOutput) -> SecurityAgentOutput:
        """Run security branch analysis."""

    def run_performance(self, scanner_output: ScannerOutput) -> PerformanceAgentOutput:
        """Run performance branch analysis."""


class HeuristicBranchExecutor:
    """Deterministic evidence-driven branch analyzer."""

    def run_architecture(self, scanner_output: ScannerOutput) -> ArchitectureAgentOutput:
        architecture_type = _infer_architecture_type(scanner_output)
        module_boundaries = [
            ModuleBoundary(
                name=folder.path,
                paths=[folder.path],
                responsibility=folder.purpose_guess,
            )
            for folder in scanner_output.folders[:10]
        ]
        runtime_summary = _runtime_flow_summary(scanner_output)

        findings: list[BaseFinding] = []
        evidence_item = _first_evidence(scanner_output, {"entrypoint", "route", "config"})
        if evidence_item:
            findings.append(
                BaseFinding(
                    id=_finding_id("architecture", evidence_item.file, evidence_item.summary),
                    category=FindingCategory.ARCHITECTURE,
                    title="Detected runtime entrypoint and module layering",
                    description=(
                        "Repository layout indicates a bounded runtime flow with clear "
                        "entrypoint/module segmentation."
                    ),
                    severity=Severity.LOW,
                    status=FindingStatus.CONFIRMED,
                    confidence=0.75,
                    symptoms=["Module boundaries are inferable from folder structure"],
                    recommendation="Document runtime boundaries in architecture docs.",
                    evidence=[_to_finding_evidence(evidence_item)],
                )
            )
        else:
            findings.append(
                BaseFinding(
                    id=_finding_id("architecture", scanner_output.repo_profile.repo_name, "unknown"),
                    category=FindingCategory.ARCHITECTURE,
                    title="Insufficient architecture evidence",
                    description=(
                        "Scanner produced limited architecture evidence for confident "
                        "pattern classification."
                    ),
                    severity=Severity.MEDIUM,
                    status=FindingStatus.INSUFFICIENT_EVIDENCE,
                    confidence=0.35,
                    symptoms=["Architecture type may be under-specified"],
                    recommendation="Increase scanner depth for routing and service boundaries.",
                )
            )

        return ArchitectureAgentOutput(
            schema_version=scanner_output.schema_version,
            run_id=scanner_output.run_id,
            architecture_type=architecture_type,
            module_boundaries=module_boundaries,
            runtime_flow_summary=runtime_summary,
            findings=findings,
        )

    def run_security(self, scanner_output: ScannerOutput) -> SecurityAgentOutput:
        security_evidence = [
            evidence
            for evidence in scanner_output.evidence_index
            if evidence.source in {"semgrep", "bandit", "osv"}
            or evidence.signal_type in {"secret", "vuln", "dependency"}
        ]
        findings: list[BaseFinding] = []
        top_risks: list[SecurityRisk] = []

        for evidence in security_evidence[:10]:
            severity = _security_severity(evidence)
            finding = BaseFinding(
                id=_finding_id("security", evidence.file, evidence.summary),
                category=FindingCategory.SECURITY,
                title=f"Security signal from {evidence.source}",
                description=evidence.summary,
                severity=severity,
                status=FindingStatus.CONFIRMED,
                confidence=min(0.95, max(0.6, evidence.confidence)),
                symptoms=["Potential exploit surface detected in static evidence"],
                recommendation=_security_recommendation(evidence),
                evidence=[_to_finding_evidence(evidence)],
            )
            findings.append(finding)
            top_risks.append(
                SecurityRisk(
                    issue=finding.title,
                    severity=finding.severity,
                    file=evidence.file,
                )
            )

        if not findings:
            findings.append(
                BaseFinding(
                    id=_finding_id("security", scanner_output.repo_profile.repo_name, "none"),
                    category=FindingCategory.SECURITY,
                    title="No deterministic security evidence found",
                    description="No semgrep/bandit/osv/secret evidence was available for confirmation.",
                    severity=Severity.LOW,
                    status=FindingStatus.INSUFFICIENT_EVIDENCE,
                    confidence=0.3,
                    symptoms=["Security branch could not confirm concrete risks"],
                    recommendation="Enable Semgrep/Bandit/OSV and rescan for higher confidence.",
                )
            )

        return SecurityAgentOutput(
            schema_version=scanner_output.schema_version,
            run_id=scanner_output.run_id,
            findings=findings,
            top_security_risks=top_risks[:5],
        )

    def run_performance(self, scanner_output: ScannerOutput) -> PerformanceAgentOutput:
        performance_evidence = [
            evidence
            for evidence in scanner_output.evidence_index
            if evidence.signal_type == "perf_hotspot"
            or _contains_perf_signal(evidence.summary)
        ]
        findings: list[BaseFinding] = []
        top_risks: list[PerformanceRisk] = []

        for evidence in performance_evidence[:10]:
            finding = BaseFinding(
                id=_finding_id("performance", evidence.file, evidence.summary),
                category=FindingCategory.PERFORMANCE,
                title="Potential performance/scalability signal detected",
                description=evidence.summary,
                severity=Severity.MEDIUM,
                status=FindingStatus.CONFIRMED,
                confidence=min(0.9, max(0.55, evidence.confidence)),
                symptoms=["Potential latency or throughput degradation"],
                recommendation="Review the identified hotspot and add batching/caching/pagination as needed.",
                evidence=[_to_finding_evidence(evidence)],
            )
            findings.append(finding)
            top_risks.append(
                PerformanceRisk(
                    issue=finding.title,
                    severity=finding.severity,
                    file=evidence.file,
                )
            )

        if not findings:
            route_evidence = _first_evidence(scanner_output, {"route", "entrypoint"})
            if route_evidence:
                findings.append(
                    BaseFinding(
                        id=_finding_id("performance", route_evidence.file, "api-pagination"),
                        category=FindingCategory.PERFORMANCE,
                        title="API pagination and caching require review",
                        description="API surface detected; pagination/caching guarantees are not yet evidenced.",
                        severity=Severity.MEDIUM,
                        status=FindingStatus.SUSPECTED,
                        confidence=0.45,
                        symptoms=["Large payload and latency risk on list endpoints"],
                        recommendation="Audit list endpoints for pagination and response-size controls.",
                        evidence=[_to_finding_evidence(route_evidence)],
                    )
                )
                top_risks.append(
                    PerformanceRisk(
                        issue="Review pagination/caching on API routes",
                        severity=Severity.MEDIUM,
                        file=route_evidence.file,
                    )
                )
            else:
                findings.append(
                    BaseFinding(
                        id=_finding_id("performance", scanner_output.repo_profile.repo_name, "none"),
                        category=FindingCategory.PERFORMANCE,
                        title="Insufficient performance evidence",
                        description="No deterministic performance hotspots were detected.",
                        severity=Severity.LOW,
                        status=FindingStatus.INSUFFICIENT_EVIDENCE,
                        confidence=0.3,
                        symptoms=["No clear bottlenecks identified from current evidence"],
                        recommendation="Expand scanner heuristics for query and I/O hotspot detection.",
                    )
                )

        return PerformanceAgentOutput(
            schema_version=scanner_output.schema_version,
            run_id=scanner_output.run_id,
            findings=findings,
            top_performance_risks=top_risks[:5],
        )


class CrewBranchExecutor:
    """CrewAI-backed branch executor with strict output contracts."""

    def __init__(
        self,
        *,
        config: AppConfig,
        model_factory: ModelFactory,
        provider_profile: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.config = config
        self.model_factory = model_factory
        self.provider_profile = provider_profile
        self.env = env or dict(os.environ)
        profile = self.model_factory.get_profile(provider_profile)
        self._token_budgeter = TokenBudgeter(profile.model)

    def run_architecture(self, scanner_output: ScannerOutput) -> ArchitectureAgentOutput:
        task_description = (
            "Analyze repository scanner evidence and return ArchitectureAgentOutput JSON. "
            "Use only supplied evidence and include confidence and citations."
        )
        expected = "Structured ArchitectureAgentOutput with architecture findings."
        context = self._serialize_context(
            scanner_output, self.config.token_budgets.architecture_context
        )
        output = self._run_task(
            role="Architecture Analyst Agent",
            goal="Infer architecture type, module boundaries, and runtime flow from scanner evidence.",
            backstory="Specialist in architecture inference with strict evidence-first reasoning.",
            task_description=f"{task_description}\n\nScanner context:\n{context}",
            expected_output=expected,
            output_model=ArchitectureAgentOutput,
        )
        return self._normalize_output_metadata(output, scanner_output)

    def run_security(self, scanner_output: ScannerOutput) -> SecurityAgentOutput:
        task_description = (
            "Analyze scanner security evidence and return SecurityAgentOutput JSON. "
            "Report only evidence-linked risks with explicit severity and fixes."
        )
        expected = "Structured SecurityAgentOutput with top security risks and findings."
        context = self._serialize_context(scanner_output, self.config.token_budgets.security_context)
        output = self._run_task(
            role="Security Risk Agent",
            goal="Identify concrete security risks and remediation guidance from repository evidence.",
            backstory="AppSec reviewer focused on deterministic static-analysis signals.",
            task_description=f"{task_description}\n\nScanner context:\n{context}",
            expected_output=expected,
            output_model=SecurityAgentOutput,
        )
        return self._normalize_output_metadata(output, scanner_output)

    def run_performance(self, scanner_output: ScannerOutput) -> PerformanceAgentOutput:
        task_description = (
            "Analyze scanner performance evidence and return PerformanceAgentOutput JSON. "
            "Prioritize scalability bottlenecks with symptoms and recommendations."
        )
        expected = "Structured PerformanceAgentOutput with top performance risks and findings."
        context = self._serialize_context(
            scanner_output, self.config.token_budgets.performance_context
        )
        output = self._run_task(
            role="Performance Analyst Agent",
            goal="Detect bottlenecks and scalability risks from deterministic scanner signals.",
            backstory="Performance engineer prioritizing concrete, reproducible evidence.",
            task_description=f"{task_description}\n\nScanner context:\n{context}",
            expected_output=expected,
            output_model=PerformanceAgentOutput,
        )
        return self._normalize_output_metadata(output, scanner_output)

    def _run_task(
        self,
        *,
        role: str,
        goal: str,
        backstory: str,
        task_description: str,
        expected_output: str,
        output_model: type[MODEL_T],
    ) -> MODEL_T:
        llm = self.model_factory.create_llm(
            profile_name=self.provider_profile,
            env=self.env,
        )
        agent = Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            llm=llm,
            allow_delegation=False,
            verbose=False,
        )
        task = Task(
            description=task_description,
            expected_output=expected_output,
            output_pydantic=output_model,
            agent=agent,
        )
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        if getattr(result, "pydantic", None) is not None:
            pydantic_result = result.pydantic
            if isinstance(pydantic_result, output_model):
                return pydantic_result
        if getattr(result, "tasks_output", None):
            task_output = result.tasks_output[-1]
            if getattr(task_output, "pydantic", None) is not None and isinstance(
                task_output.pydantic, output_model
            ):
                return task_output.pydantic
            if getattr(task_output, "json_dict", None) is not None:
                return output_model.model_validate(task_output.json_dict)
        if getattr(result, "json_dict", None) is not None:
            return output_model.model_validate(result.json_dict)
        raw = getattr(result, "raw", None)
        if raw:
            return output_model.model_validate_json(raw)
        raise ValueError("Crew output did not contain parseable structured data")

    def _serialize_context(self, scanner_output: ScannerOutput, budget: int) -> str:
        scanner_payload = scanner_output.model_dump(mode="json")
        context = orjson.dumps(scanner_payload, option=orjson.OPT_SORT_KEYS).decode("utf-8")
        self._token_budgeter.ensure_within_budget(context, budget)
        return context

    @staticmethod
    def _normalize_output_metadata(model: MODEL_T, scanner_output: ScannerOutput) -> MODEL_T:
        updates: dict[str, Any] = {
            "schema_version": scanner_output.schema_version,
            "run_id": scanner_output.run_id,
        }
        return model.model_copy(update=updates)


def build_failed_architecture_output(
    *, run_id: str, schema_version: str, reason: str
) -> ArchitectureAgentOutput:
    """Create failed architecture output payload."""
    return ArchitectureAgentOutput(
        schema_version=schema_version,
        run_id=run_id,
        architecture_type=ArchitectureType.UNKNOWN,
        runtime_flow_summary=f"Architecture branch failed: {reason}",
        findings=[
            BaseFinding(
                id=_finding_id("architecture", run_id, "failed"),
                category=FindingCategory.ARCHITECTURE,
                title="Architecture branch execution failed",
                description=reason,
                severity=Severity.MEDIUM,
                status=FindingStatus.FAILED,
                confidence=0.0,
                symptoms=["Architecture analysis could not complete"],
                recommendation="Review branch execution logs and rerun.",
            )
        ],
    )


def build_failed_security_output(
    *, run_id: str, schema_version: str, reason: str
) -> SecurityAgentOutput:
    """Create failed security output payload."""
    return SecurityAgentOutput(
        schema_version=schema_version,
        run_id=run_id,
        findings=[
            BaseFinding(
                id=_finding_id("security", run_id, "failed"),
                category=FindingCategory.SECURITY,
                title="Security branch execution failed",
                description=reason,
                severity=Severity.HIGH,
                status=FindingStatus.FAILED,
                confidence=0.0,
                symptoms=["Security analysis unavailable"],
                recommendation="Inspect branch execution failure and rerun security stage.",
            )
        ],
        top_security_risks=[],
    )


def build_failed_performance_output(
    *, run_id: str, schema_version: str, reason: str
) -> PerformanceAgentOutput:
    """Create failed performance output payload."""
    return PerformanceAgentOutput(
        schema_version=schema_version,
        run_id=run_id,
        findings=[
            BaseFinding(
                id=_finding_id("performance", run_id, "failed"),
                category=FindingCategory.PERFORMANCE,
                title="Performance branch execution failed",
                description=reason,
                severity=Severity.MEDIUM,
                status=FindingStatus.FAILED,
                confidence=0.0,
                symptoms=["Performance branch unavailable"],
                recommendation="Inspect branch execution failure and rerun performance stage.",
            )
        ],
        top_performance_risks=[],
    )


def synthesize_roadmap(
    *,
    architecture_output: ArchitectureAgentOutput,
    security_output: SecurityAgentOutput,
    performance_output: PerformanceAgentOutput,
) -> list[RoadmapItem]:
    """Generate deterministic roadmap items from branch findings."""
    findings = [
        *architecture_output.findings,
        *security_output.findings,
        *performance_output.findings,
    ]
    actionable = [
        finding
        for finding in findings
        if finding.status in {FindingStatus.CONFIRMED, FindingStatus.SUSPECTED}
    ]
    sorted_findings = sorted(
        actionable,
        key=lambda item: (
            SEVERITY_ORDER.get(item.severity, 4),
            1 - item.confidence,
        ),
    )
    roadmap_items: list[RoadmapItem] = []
    for finding in sorted_findings[:10]:
        priority = (
            "P0"
            if finding.severity in {Severity.CRITICAL, Severity.HIGH}
            else "P1"
            if finding.severity == Severity.MEDIUM
            else "P2"
        )
        timeline = (
            "immediate_1_2_days"
            if priority == "P0"
            else "short_term_1_2_weeks"
            if priority == "P1"
            else "medium_term_1_2_months"
        )
        roadmap_items.append(
            RoadmapItem(
                priority=priority,
                task=finding.recommendation,
                impact=f"Mitigates {finding.category.value} risk: {finding.title}",
                effort="Medium",
                risk=finding.severity.value,
                justification=finding.description,
                timeline_bucket=timeline,
                depends_on=[finding.id],
            )
        )
    return roadmap_items


def _infer_architecture_type(scanner_output: ScannerOutput) -> ArchitectureType:
    hints = {hint.lower() for hint in scanner_output.repo_profile.architecture_hints}
    if any("microservice" in hint for hint in hints):
        return ArchitectureType.MICROSERVICES
    if any("modular" in hint for hint in hints):
        return ArchitectureType.MODULAR_MONOLITH
    if scanner_output.repo_profile.entry_points:
        return ArchitectureType.MONOLITH
    return ArchitectureType.UNKNOWN


def _runtime_flow_summary(scanner_output: ScannerOutput) -> str:
    entrypoints = scanner_output.repo_profile.entry_points
    if not entrypoints:
        return "Runtime flow is uncertain due to limited entrypoint evidence."
    return (
        f"Runtime likely starts from {', '.join(entrypoints[:3])}, then routes through "
        "module boundaries inferred from top-level folders."
    )


def _first_evidence(
    scanner_output: ScannerOutput, signal_types: set[str]
) -> EvidenceItem | None:
    for evidence in scanner_output.evidence_index:
        if evidence.signal_type in signal_types:
            return evidence
    return None


def _to_finding_evidence(evidence: EvidenceItem) -> FindingEvidence:
    return FindingEvidence(
        file=evidence.file,
        line_start=evidence.line_start,
        line_end=evidence.line_end,
        source=evidence.source,
        rule_id=None,
    )


def _security_severity(evidence: EvidenceItem) -> Severity:
    if evidence.signal_type in {"secret", "vuln"}:
        return Severity.HIGH
    if evidence.signal_type == "dependency":
        return Severity.MEDIUM
    return Severity.LOW


def _security_recommendation(evidence: EvidenceItem) -> str:
    if evidence.signal_type == "secret":
        return "Rotate the secret and move credentials to environment/config vault."
    if evidence.signal_type == "dependency":
        return "Upgrade affected dependency and pin a patched version."
    return "Review and remediate the reported vulnerability pattern."


def _contains_perf_signal(summary: str) -> bool:
    lowered = summary.lower()
    keywords = ["n+1", "synchronous", "sync", "pagination", "cache", "payload", "latency"]
    return any(keyword in lowered for keyword in keywords)


def _finding_id(category: str, file_ref: str, seed: str) -> str:
    digest = hashlib.sha256(f"{category}:{file_ref}:{seed}".encode("utf-8")).hexdigest()
    return digest[:16]
