"""Branch executor implementations for phase 5."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Protocol, TypeVar

import orjson
from crewai import Agent, Crew, Process, Task
from pydantic import BaseModel, Field

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
from repoclinic.schemas.enums import (
    ArchitectureType,
    FindingCategory,
    FindingStatus,
    Priority,
    Severity,
)
from repoclinic.schemas.output_models import RoadmapItem, TimelineBucket
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

    def run_architecture(
        self, scanner_output: ScannerOutput
    ) -> ArchitectureAgentOutput:
        """Run architecture branch analysis."""

    def run_security(self, scanner_output: ScannerOutput) -> SecurityAgentOutput:
        """Run security branch analysis."""

    def run_performance(self, scanner_output: ScannerOutput) -> PerformanceAgentOutput:
        """Run performance branch analysis."""

    def run_roadmap(
        self,
        architecture_output: ArchitectureAgentOutput,
        security_output: SecurityAgentOutput,
        performance_output: PerformanceAgentOutput,
    ) -> list[RoadmapItem]:
        """Run roadmap planning from branch outputs."""


class RoadmapPlannerOutput(BaseModel):
    """CrewAI roadmap planner response envelope."""

    items: list[RoadmapItem] = Field(default_factory=list)


class HeuristicBranchExecutor:
    """Deterministic evidence-driven branch analyzer."""

    def run_architecture(
        self, scanner_output: ScannerOutput
    ) -> ArchitectureAgentOutput:
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
        evidence_item = _first_evidence(
            scanner_output, {"entrypoint", "route", "config"}
        )
        if evidence_item:
            findings.append(
                BaseFinding(
                    id=_finding_id(
                        "architecture", evidence_item.file, evidence_item.summary
                    ),
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
                    id=_finding_id(
                        "architecture", scanner_output.repo_profile.repo_name, "unknown"
                    ),
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
            or evidence.signal_type in {"secret", "vuln", "auth", "route"}
            or (evidence.signal_type == "dependency" and evidence.source == "osv")
        ]
        checklist: list[tuple[str, str, Severity, list[str], str, str]] = [
            (
                "hardcoded-secrets",
                "Hardcoded secrets review",
                Severity.HIGH,
                ["secret", "token", "api key", "apikey", "credential"],
                "Credential leakage can lead to direct account or infrastructure compromise.",
                "Move secrets to environment or vault storage, rotate exposed values, and add secret scanning gates.",
            ),
            (
                "unsafe-config-practices",
                "Unsafe configuration practices review",
                Severity.MEDIUM,
                ["debug", "insecure", "cors", "allow all", "unsafe config"],
                "Insecure defaults can expose sensitive data and increase attack surface.",
                "Harden security configuration defaults and enforce secure production profiles.",
            ),
            (
                "missing-input-validation",
                "Input validation coverage review",
                Severity.HIGH,
                ["input validation", "unsanitized", "tainted", "user input"],
                "Unvalidated user input can enable injection and authorization bypass paths.",
                "Add schema-based request validation and sanitization at API boundaries.",
            ),
            (
                "sql-injection-patterns",
                "SQL injection pattern review",
                Severity.HIGH,
                ["sql injection", "raw sql", "execute(", "query concatenation"],
                "Unsafe query construction can allow unauthorized data access or mutation.",
                "Use parameterized queries and ORM safe APIs for all database access paths.",
            ),
            (
                "insecure-jwt-usage",
                "JWT security review",
                Severity.HIGH,
                ["jwt", "none algorithm", "weak signing", "token verify"],
                "JWT validation mistakes can allow token forgery or privilege escalation.",
                "Enforce strong algorithms, audience/issuer validation, and token expiry checks.",
            ),
            (
                "weak-password-storage",
                "Password storage review",
                Severity.HIGH,
                ["plaintext password", "md5", "sha1", "weak hash", "password storage"],
                "Weak password hashing allows credential cracking and account takeover.",
                "Use adaptive password hashing (bcrypt/argon2) with salts and controlled cost factors.",
            ),
            (
                "exposed-admin-endpoints",
                "Admin endpoint access-control review",
                Severity.HIGH,
                ["admin", "management endpoint", "internal endpoint", "/admin"],
                "Unauthenticated admin endpoints can expose sensitive operations.",
                "Protect admin routes with authentication, authorization, and network restrictions.",
            ),
            (
                "dependency-vulnerabilities",
                "Dependency vulnerability review",
                Severity.MEDIUM,
                ["vulnerable", "dependency", "osv", "cve", "ghsa"],
                "Known vulnerable dependencies increase exploitability of deployed systems.",
                "Upgrade vulnerable dependencies to patched versions and enforce lockfile hygiene.",
            ),
        ]

        findings: list[BaseFinding] = []
        for check_id, title, severity, keywords, symptoms, recommendation in checklist:
            evidence = _find_matching_evidence(security_evidence, keywords)
            findings.append(
                _build_check_finding(
                    scanner_output=scanner_output,
                    category=FindingCategory.SECURITY,
                    check_id=check_id,
                    title=title,
                    severity=severity,
                    symptoms=symptoms,
                    recommendation=recommendation,
                    evidence=evidence,
                )
            )

        dependency_summary = scanner_output.dependency_summary
        if (
            dependency_summary.vulnerability_scan_status == "completed"
            and dependency_summary.vulnerability_findings
        ):
            dependency_evidence = [
                _to_finding_evidence(dependency_item)
                for dependency_item in security_evidence
                if dependency_item.source == "osv"
            ][:3]
            findings.append(
                BaseFinding(
                    id=_finding_id(
                        "security",
                        scanner_output.repo_profile.repo_name,
                        "dependency-findings-present",
                    ),
                    category=FindingCategory.SECURITY,
                    title="Dependency vulnerabilities confirmed by OSV",
                    description=(
                        f"OSV reported {len(dependency_summary.vulnerability_findings)} dependency vulnerabilities."
                    ),
                    severity=Severity.HIGH,
                    status=(
                        FindingStatus.CONFIRMED
                        if dependency_evidence
                        else FindingStatus.SUSPECTED
                    ),
                    confidence=0.9,
                    symptoms=[
                        "Known vulnerable packages are present in dependency manifests"
                    ],
                    recommendation="Prioritize patch upgrades for direct and transitive vulnerable packages.",
                    evidence=dependency_evidence,
                )
            )

        top_risks = _top_security_risks(findings)
        return SecurityAgentOutput(
            schema_version=scanner_output.schema_version,
            run_id=scanner_output.run_id,
            findings=findings,
            top_security_risks=top_risks,
        )

    def run_performance(self, scanner_output: ScannerOutput) -> PerformanceAgentOutput:
        performance_evidence = [
            evidence
            for evidence in scanner_output.evidence_index
            if evidence.signal_type == "perf_hotspot"
            or _contains_perf_signal(evidence.summary)
        ]
        checklist: list[tuple[str, str, Severity, list[str], str, str]] = [
            (
                "heavy-sync-operations",
                "Heavy synchronous operation review",
                Severity.MEDIUM,
                ["synchronous", "sync", "blocking", "await-less"],
                "Blocking operations can increase response latency and reduce throughput under load.",
                "Move blocking workloads off hot request paths and prefer asynchronous/background processing.",
            ),
            (
                "n-plus-one-query-patterns",
                "N+1 query pattern review",
                Severity.HIGH,
                ["n+1", "multiple query", "query per item", "loop query"],
                "N+1 access patterns create multiplicative latency and database pressure.",
                "Batch related fetches and use eager-loading or prefetch strategies for dependent data.",
            ),
            (
                "missing-caching-opportunities",
                "Caching opportunity review",
                Severity.MEDIUM,
                ["cache", "no cache", "recompute", "repeat query"],
                "Missing caches can increase compute and database cost for repeated reads.",
                "Introduce response/query caching with clear invalidation and bounded TTL policies.",
            ),
            (
                "large-payload-risks",
                "Large payload risk review",
                Severity.MEDIUM,
                ["payload", "large response", "serialize", "memory growth"],
                "Oversized payloads increase bandwidth and memory overhead at runtime.",
                "Add field filtering, compression, and payload size limits on expensive endpoints.",
            ),
            (
                "db-indexing-hints",
                "Database indexing review",
                Severity.MEDIUM,
                ["index", "full scan", "table scan", "order by"],
                "Missing indexes can cause full table scans and high query latency.",
                "Review frequent filters/sorts and add supporting indexes for dominant access patterns.",
            ),
            (
                "loop-and-io-hotspots",
                "Loop and file I/O hotspot review",
                Severity.MEDIUM,
                ["loop", "file io", "read file", "write file", "iterative"],
                "Unbounded loops and heavy I/O can cause CPU spikes and request stalls.",
                "Profile loop-heavy and file I/O paths, then batch, stream, or debounce operations.",
            ),
            (
                "missing-pagination-in-apis",
                "API pagination review",
                Severity.HIGH,
                ["pagination", "list endpoint", "all records", "offset", "limit"],
                "Unpaginated list endpoints can trigger high memory use and slow responses.",
                "Require pagination parameters and enforce safe page-size defaults on list APIs.",
            ),
        ]
        findings = [
            _build_check_finding(
                scanner_output=scanner_output,
                category=FindingCategory.PERFORMANCE,
                check_id=check_id,
                title=title,
                severity=severity,
                symptoms=symptoms,
                recommendation=recommendation,
                evidence=_find_matching_evidence(performance_evidence, keywords),
            )
            for check_id, title, severity, keywords, symptoms, recommendation in checklist
        ]
        top_risks = _top_performance_risks(findings)
        return PerformanceAgentOutput(
            schema_version=scanner_output.schema_version,
            run_id=scanner_output.run_id,
            findings=findings,
            top_performance_risks=top_risks,
        )

    def run_roadmap(
        self,
        architecture_output: ArchitectureAgentOutput,
        security_output: SecurityAgentOutput,
        performance_output: PerformanceAgentOutput,
    ) -> list[RoadmapItem]:
        return synthesize_roadmap(
            architecture_output=architecture_output,
            security_output=security_output,
            performance_output=performance_output,
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

    def run_architecture(
        self, scanner_output: ScannerOutput
    ) -> ArchitectureAgentOutput:
        task_description = (
            "Analyze repository scanner evidence and return ArchitectureAgentOutput JSON. "
            "Use only supplied evidence and include confidence and citations. "
            "Status contract: use 'failed' only if branch execution itself failed; "
            "use 'insufficient_evidence' when evidence is missing and 'suspected' when uncertain."
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
            "Report only evidence-linked risks with explicit severity and fixes. "
            "Explicitly assess: hardcoded secrets, unsafe config practices, missing input validation, "
            "SQL injection patterns, insecure JWT usage, weak password storage, exposed admin endpoints, "
            "and dependency vulnerabilities. "
            "Status contract: use 'failed' only if branch execution itself failed; "
            "use 'insufficient_evidence' when evidence is missing and 'suspected' when uncertain."
        )
        expected = (
            "Structured SecurityAgentOutput with top security risks and findings."
        )
        context = self._serialize_context(
            scanner_output, self.config.token_budgets.security_context
        )
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
            "Prioritize scalability bottlenecks with symptoms and recommendations. "
            "Explicitly assess: heavy synchronous operations, N+1 query patterns, missing caching, "
            "large payload risk, indexing hints, loop/file-I/O hotspots, and missing pagination. "
            "Status contract: use 'failed' only if branch execution itself failed; "
            "use 'insufficient_evidence' when evidence is missing and 'suspected' when uncertain."
        )
        expected = (
            "Structured PerformanceAgentOutput with top performance risks and findings."
        )
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

    def run_roadmap(
        self,
        architecture_output: ArchitectureAgentOutput,
        security_output: SecurityAgentOutput,
        performance_output: PerformanceAgentOutput,
    ) -> list[RoadmapItem]:
        task_description = (
            "Consolidate architecture, security, and performance findings and return "
            "RoadmapPlannerOutput JSON with an 'items' list of RoadmapItem objects. "
            "Each item must include priority, impact, effort, risk, and justification."
        )
        expected = "Structured RoadmapPlannerOutput with prioritized roadmap items."
        context_payload = {
            "architecture": architecture_output.model_dump(mode="json"),
            "security": security_output.model_dump(mode="json"),
            "performance": performance_output.model_dump(mode="json"),
        }
        context = orjson.dumps(context_payload, option=orjson.OPT_SORT_KEYS).decode(
            "utf-8"
        )
        self._token_budgeter.ensure_within_budget(
            context, self.config.token_budgets.roadmap_context
        )
        output = self._run_task(
            role="Roadmap Planner Agent",
            goal="Produce a realistic, prioritized engineering roadmap from validated findings.",
            backstory="Technical planner focused on actionable sequencing and execution risk management.",
            task_description=f"{task_description}\n\nBranch context:\n{context}",
            expected_output=expected,
            output_model=RoadmapPlannerOutput,
        )
        return output.items

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
        result: Any = crew.kickoff()
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
        context = orjson.dumps(scanner_payload, option=orjson.OPT_SORT_KEYS).decode(
            "utf-8"
        )
        self._token_budgeter.ensure_within_budget(context, budget)
        return context

    @staticmethod
    def _normalize_output_metadata(
        model: MODEL_T, scanner_output: ScannerOutput
    ) -> MODEL_T:
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
        priority: Priority
        if finding.severity in {Severity.CRITICAL, Severity.HIGH}:
            priority = Priority.P0
        elif finding.severity == Severity.MEDIUM:
            priority = Priority.P1
        else:
            priority = Priority.P2
        timeline: TimelineBucket
        if priority == Priority.P0:
            timeline = "immediate_1_2_days"
        elif priority == Priority.P1:
            timeline = "short_term_1_2_weeks"
        else:
            timeline = "medium_term_1_2_months"
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


def _find_matching_evidence(
    evidence_items: list[EvidenceItem], keywords: list[str]
) -> EvidenceItem | None:
    normalized_keywords = [keyword.lower() for keyword in keywords]
    for evidence in evidence_items:
        haystack = f"{evidence.summary} {evidence.file}".lower()
        if any(keyword in haystack for keyword in normalized_keywords):
            return evidence
    return None


def _build_check_finding(
    *,
    scanner_output: ScannerOutput,
    category: FindingCategory,
    check_id: str,
    title: str,
    severity: Severity,
    symptoms: str,
    recommendation: str,
    evidence: EvidenceItem | None,
) -> BaseFinding:
    if evidence is None:
        return BaseFinding(
            id=_finding_id(
                category.value, scanner_output.repo_profile.repo_name, check_id
            ),
            category=category,
            title=title,
            description=(
                f"No deterministic evidence confirmed this check: {title.lower()}."
            ),
            severity=severity,
            status=FindingStatus.INSUFFICIENT_EVIDENCE,
            confidence=0.35,
            symptoms=[symptoms],
            recommendation=recommendation,
        )

    status = (
        FindingStatus.CONFIRMED
        if evidence.confidence >= 0.7
        else FindingStatus.SUSPECTED
    )
    return BaseFinding(
        id=_finding_id(category.value, evidence.file, check_id),
        category=category,
        title=title,
        description=evidence.summary,
        severity=severity,
        status=status,
        confidence=min(0.95, max(0.45, evidence.confidence)),
        symptoms=[symptoms],
        recommendation=recommendation,
        evidence=[_to_finding_evidence(evidence)],
    )


def _top_security_risks(findings: list[BaseFinding]) -> list[SecurityRisk]:
    actionable = [
        finding
        for finding in findings
        if finding.status in {FindingStatus.CONFIRMED, FindingStatus.SUSPECTED}
    ]
    ordered = sorted(
        actionable,
        key=lambda finding: (
            SEVERITY_ORDER.get(finding.severity, 4),
            1 - finding.confidence,
        ),
    )
    return [
        SecurityRisk(
            issue=finding.title,
            severity=finding.severity,
            file=finding.evidence[0].file if finding.evidence else "unknown",
        )
        for finding in ordered[:5]
    ]


def _top_performance_risks(findings: list[BaseFinding]) -> list[PerformanceRisk]:
    actionable = [
        finding
        for finding in findings
        if finding.status in {FindingStatus.CONFIRMED, FindingStatus.SUSPECTED}
    ]
    ordered = sorted(
        actionable,
        key=lambda finding: (
            SEVERITY_ORDER.get(finding.severity, 4),
            1 - finding.confidence,
        ),
    )
    return [
        PerformanceRisk(
            issue=finding.title,
            severity=finding.severity,
            file=finding.evidence[0].file if finding.evidence else "unknown",
        )
        for finding in ordered[:5]
    ]


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
    keywords = [
        "n+1",
        "synchronous",
        "sync",
        "pagination",
        "cache",
        "payload",
        "latency",
    ]
    return any(keyword in lowered for keyword in keywords)


def _finding_id(category: str, file_ref: str, seed: str) -> str:
    digest = hashlib.sha256(f"{category}:{file_ref}:{seed}".encode("utf-8")).hexdigest()
    return digest[:16]
