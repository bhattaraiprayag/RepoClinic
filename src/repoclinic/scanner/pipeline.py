"""Phase 3 deterministic scanner pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from repoclinic.config.models import AppConfig
from repoclinic.scanner.heuristics import (
    detect_architecture_hints,
    detect_entry_points,
    detect_frameworks,
    detect_languages,
    summarize_folders,
    summarize_manifests,
)
from repoclinic.scanner.ignore_policy import IgnorePolicy
from repoclinic.scanner.inventory import InventoryEngine
from repoclinic.scanner.normalizer import (
    build_heuristic_evidence,
    normalize_bandit,
    normalize_osv,
    normalize_semgrep,
)
from repoclinic.scanner.persistence import ScannerPersistence
from repoclinic.scanner.source_resolver import SourceResolver
from repoclinic.scanner.tool_runners import ToolRunners
from repoclinic.schemas.input_models import AnalyzeRequest
from repoclinic.schemas.scanner_models import (
    DependencyFinding,
    DependencySummary,
    RepoProfile,
    ScannerOutput,
)


class ScannerPipeline:
    """Deterministic scanner/evidence pipeline."""

    def __init__(
        self,
        *,
        config: AppConfig,
        workspace_root: Path | None = None,
        db_path: Path | None = None,
    ) -> None:
        self.config = config
        self.workspace_root = workspace_root or Path(".scanner-workspace")
        self.persistence = ScannerPersistence(db_path or Path(".sqlite/repoclinic.db"))
        self.resolver = SourceResolver(self.workspace_root)

    def run(self, request: AnalyzeRequest) -> ScannerOutput:
        """Execute deterministic scanner stage and persist outputs."""
        resolved = self.resolver.resolve(request.input, request.run_id)
        ignore_policy = IgnorePolicy.from_config(self.config.scan_policy)
        inventory_engine = InventoryEngine(ignore_policy, self.config.scan_policy)
        inventory = inventory_engine.collect(resolved.resolved_path)

        languages = detect_languages(inventory.files)
        frameworks = detect_frameworks(inventory.files)
        entry_points = detect_entry_points(inventory.files)
        architecture_hints = detect_architecture_hints(inventory.files)
        manifest_summaries = summarize_manifests(inventory.files)
        manifest_paths = [manifest.path for manifest in manifest_summaries]
        folders = summarize_folders(inventory.top_level_dirs)

        evidence = build_heuristic_evidence(
            entry_points=entry_points,
            manifests=manifest_paths,
        )
        dependency_findings: list[DependencyFinding] = []

        tool_runners = ToolRunners(
            timeout_seconds=request.execution.timeouts.scanner_seconds
        )
        tool_statuses: list[str] = []

        if self._is_enabled(
            request.execution.feature_flags.enable_semgrep,
            self.config.feature_flags.enable_semgrep,
        ):
            semgrep_result = tool_runners.run_semgrep(resolved.resolved_path)
            tool_statuses.append(semgrep_result.status)
            if semgrep_result.status == "completed":
                evidence.extend(normalize_semgrep(semgrep_result.payload))

        if "Python" in languages and self._is_enabled(
            request.execution.feature_flags.enable_bandit,
            self.config.feature_flags.enable_bandit,
        ):
            bandit_result = tool_runners.run_bandit(resolved.resolved_path)
            tool_statuses.append(bandit_result.status)
            if bandit_result.status == "completed":
                evidence.extend(normalize_bandit(bandit_result.payload))

        if self._is_enabled(
            request.execution.feature_flags.enable_osv,
            self.config.feature_flags.enable_osv,
        ):
            osv_result = tool_runners.run_osv(resolved.resolved_path)
            tool_statuses.append(osv_result.status)
            if osv_result.status == "completed":
                osv_evidence, dependency_findings = normalize_osv(osv_result.payload)
                evidence.extend(osv_evidence)

        dependency_status = _resolve_dependency_status(tool_statuses)

        scanner_output = ScannerOutput(
            schema_version=request.schema_version,
            run_id=request.run_id,
            repo_profile=RepoProfile(
                repo_name=resolved.repo_name,
                languages_detected=languages,
                frameworks_detected=frameworks,
                architecture_hints=architecture_hints,
                entry_points=entry_points,
                manifests=manifest_paths,
            ),
            scan_stats=inventory.stats,
            folders=folders,
            dependency_summary=DependencySummary(
                manifests=manifest_summaries,
                vulnerability_scan_status=dependency_status,
                vulnerability_findings=dependency_findings,
            ),
            evidence_index=evidence,
        )
        self.persistence.persist_scanner_output(
            output=scanner_output,
            resolved_path=resolved.resolved_path,
        )
        return scanner_output

    @staticmethod
    def _is_enabled(request_enabled: bool, config_enabled: bool) -> bool:
        return request_enabled and config_enabled


def _resolve_dependency_status(
    tool_statuses: list[str],
) -> Literal["completed", "failed", "unavailable"]:
    if not tool_statuses:
        return "unavailable"
    if any(status == "failed" for status in tool_statuses):
        return "failed"
    if any(status == "completed" for status in tool_statuses):
        return "completed"
    return "unavailable"
