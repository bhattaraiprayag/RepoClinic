"""Phase 4 integration tests for scanner-first flow orchestration."""

from __future__ import annotations

from pathlib import Path

from crewai.flow.persistence.sqlite import SQLiteFlowPersistence

from repoclinic.agents.executor import BranchExecutor, HeuristicBranchExecutor
from repoclinic.config.models import AppConfig
from repoclinic.flow.repoclinic_flow import RepoClinicFlow
from repoclinic.flow.transition_store import FlowTransitionStore
from repoclinic.observability.tracing import NoOpTracer
from repoclinic.resilience.retry import RetryExecutor, RetryPolicy
from repoclinic.schemas.analysis_models import (
    ArchitectureAgentOutput,
    PerformanceAgentOutput,
    SecurityAgentOutput,
)
from repoclinic.schemas.input_models import (
    AnalyzeInput,
    AnalyzeRequest,
    ExecutionConfig,
    FeatureFlags,
    ProviderConfig,
    TimeoutConfig,
)
from repoclinic.schemas.scanner_models import (
    DependencySummary,
    EvidenceItem,
    RepoProfile,
    ScanStats,
    ScannerOutput,
)


class _FakeScannerPipeline:
    def __init__(self, scanner_output: ScannerOutput) -> None:
        self.scanner_output = scanner_output
        self.calls = 0

    def run(self, _request: AnalyzeRequest) -> ScannerOutput:
        self.calls += 1
        return self.scanner_output


class _FakeBranchExecutor(BranchExecutor):
    def __init__(self, *, fail_security: bool = False) -> None:
        self.impl = HeuristicBranchExecutor()
        self.fail_security = fail_security
        self.calls = {"architecture": 0, "security": 0, "performance": 0}

    def run_architecture(
        self, scanner_output: ScannerOutput
    ) -> ArchitectureAgentOutput:
        self.calls["architecture"] += 1
        return self.impl.run_architecture(scanner_output)

    def run_security(self, scanner_output: ScannerOutput) -> SecurityAgentOutput:
        self.calls["security"] += 1
        if self.fail_security:
            raise RuntimeError("simulated security branch failure")
        return self.impl.run_security(scanner_output)

    def run_performance(self, scanner_output: ScannerOutput) -> PerformanceAgentOutput:
        self.calls["performance"] += 1
        return self.impl.run_performance(scanner_output)


def _build_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "schema_version": "1.0.0",
            "default_provider_profile": "openai-default",
            "provider_profiles": {
                "openai-default": {
                    "provider_type": "openai",
                    "model": "gpt-4.1",
                    "api_key_env": "OPENAI_API_KEY",
                    "max_tokens": 1024,
                    "capabilities": {
                        "context_window": 128000,
                        "supports_structured_output": True,
                        "retries": 3,
                    },
                }
            },
        }
    )


def _retry_executor() -> RetryExecutor:
    return RetryExecutor(
        RetryPolicy(max_attempts=1, backoff_seconds=0.0, jitter_seconds=0.0)
    )


def _scanner_output(run_id: str) -> ScannerOutput:
    return ScannerOutput(
        schema_version="1.0.0",
        run_id=run_id,
        repo_profile=RepoProfile(
            repo_name="fixture-repo",
            languages_detected=["Python"],
            frameworks_detected=["FastAPI"],
            architecture_hints=["layered-service-structure"],
            entry_points=["app.py"],
            manifests=["requirements.txt"],
        ),
        scan_stats=ScanStats(),
        dependency_summary=DependencySummary(vulnerability_scan_status="completed"),
        evidence_index=[
            EvidenceItem(
                id="e1",
                file="app.py",
                line_start=1,
                line_end=2,
                snippet_hash="hash1",
                source="scanner_heuristic",
                signal_type="entrypoint",
                summary="Entrypoint candidate: app.py",
                confidence=0.8,
            ),
            EvidenceItem(
                id="e2",
                file="app.py",
                line_start=6,
                line_end=12,
                snippet_hash="hash2",
                source="semgrep",
                signal_type="vuln",
                summary="Potential injection surface",
                confidence=0.9,
            ),
        ],
    )


def _request(run_id: str) -> AnalyzeRequest:
    return AnalyzeRequest(
        schema_version="1.0.0",
        run_id=run_id,
        input=AnalyzeInput(source_type="local_path", local_path="/tmp/repo"),
        execution=ExecutionConfig(
            provider=ProviderConfig(type="openai", model="gpt-4.1"),
            timeouts=TimeoutConfig(scanner_seconds=10, agent_seconds=10),
            feature_flags=FeatureFlags(
                enable_tree_sitter=False,
                enable_bandit=False,
                enable_semgrep=False,
                enable_osv=False,
            ),
        ),
    )


def test_flow_fan_out_fan_in_and_transition_log(tmp_path: Path) -> None:
    """Flow should execute scanner -> parallel branches -> roadmap trigger."""
    run_id = "flow-run-1"
    db_path = tmp_path / "flow.db"
    scanner_pipeline = _FakeScannerPipeline(_scanner_output(run_id))
    branch_executor = _FakeBranchExecutor()
    transition_store = FlowTransitionStore(db_path)
    flow = RepoClinicFlow(
        config=_build_config(),
        scanner_pipeline=scanner_pipeline,
        transition_store=transition_store,
        branch_executor=branch_executor,
        retry_executor=_retry_executor(),
        tracer=NoOpTracer(),
        persistence=SQLiteFlowPersistence(db_path=str(db_path)),
    )
    request = _request(run_id)

    flow.kickoff(
        inputs={
            "id": run_id,
            "request_payload": request.model_dump(mode="json"),
            "run_id": run_id,
            "schema_version": "1.0.0",
            "provider_profile": "openai-default",
        }
    )

    assert flow.state.branch_statuses["scanner"] == "completed"
    assert flow.state.branch_statuses["architecture"] == "completed"
    assert flow.state.branch_statuses["security"] == "completed"
    assert flow.state.branch_statuses["performance"] == "completed"
    assert flow.state.branch_statuses["roadmap"] == "completed"
    assert scanner_pipeline.calls == 1
    assert branch_executor.calls == {"architecture": 1, "security": 1, "performance": 1}

    transitions = transition_store.list_transitions(run_id)
    node_names = [entry[0] for entry in transitions]
    assert "start" in node_names
    assert "scanner" in node_names
    assert "architecture" in node_names
    assert "security" in node_names
    assert "performance" in node_names
    assert node_names[-1] == "roadmap"

    branch_terminal_indexes = [
        idx
        for idx, entry in enumerate(transitions)
        if entry[0] in {"architecture", "security", "performance"}
        and entry[2] in {"completed", "failed"}
    ]
    roadmap_running_index = next(
        idx
        for idx, entry in enumerate(transitions)
        if entry[0] == "roadmap" and entry[2] == "running"
    )
    assert roadmap_running_index > max(branch_terminal_indexes)


def test_flow_partial_failure_still_reaches_roadmap(tmp_path: Path) -> None:
    """Roadmap should complete in degraded mode when a branch fails."""
    run_id = "flow-run-2"
    db_path = tmp_path / "flow.db"
    flow = RepoClinicFlow(
        config=_build_config(),
        scanner_pipeline=_FakeScannerPipeline(_scanner_output(run_id)),
        transition_store=FlowTransitionStore(db_path),
        branch_executor=_FakeBranchExecutor(fail_security=True),
        retry_executor=_retry_executor(),
        tracer=NoOpTracer(),
        persistence=SQLiteFlowPersistence(db_path=str(db_path)),
    )
    request = _request(run_id)

    flow.kickoff(
        inputs={
            "id": run_id,
            "request_payload": request.model_dump(mode="json"),
            "run_id": run_id,
            "schema_version": "1.0.0",
            "provider_profile": "openai-default",
        }
    )

    assert flow.state.branch_statuses["security"] == "failed"
    assert flow.state.branch_statuses["roadmap"] == "degraded"
    assert flow.state.roadmap_output is not None
    assert "security" in flow.state.branch_failures


def test_flow_resume_uses_idempotency_guards(tmp_path: Path) -> None:
    """Resuming by run_id should avoid duplicate scanner/branch execution."""
    run_id = "flow-run-3"
    db_path = tmp_path / "flow.db"
    scanner_pipeline = _FakeScannerPipeline(_scanner_output(run_id))
    branch_executor = _FakeBranchExecutor()
    request = _request(run_id)

    first_flow = RepoClinicFlow(
        config=_build_config(),
        scanner_pipeline=scanner_pipeline,
        transition_store=FlowTransitionStore(db_path),
        branch_executor=branch_executor,
        retry_executor=_retry_executor(),
        tracer=NoOpTracer(),
        persistence=SQLiteFlowPersistence(db_path=str(db_path)),
    )
    first_flow.kickoff(
        inputs={
            "id": run_id,
            "request_payload": request.model_dump(mode="json"),
            "run_id": run_id,
            "schema_version": "1.0.0",
            "provider_profile": "openai-default",
        }
    )

    resumed_flow = RepoClinicFlow(
        config=_build_config(),
        scanner_pipeline=scanner_pipeline,
        transition_store=FlowTransitionStore(db_path),
        branch_executor=branch_executor,
        retry_executor=_retry_executor(),
        tracer=NoOpTracer(),
        persistence=SQLiteFlowPersistence(db_path=str(db_path)),
    )
    resumed_flow.kickoff(inputs={"id": run_id})

    assert scanner_pipeline.calls == 1
    assert branch_executor.calls == {"architecture": 1, "security": 1, "performance": 1}
    assert resumed_flow.state.completed_nodes
