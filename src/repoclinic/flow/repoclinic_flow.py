"""ARC-FL2 stateful flow orchestration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from crewai.flow import Flow, and_, listen, start
from crewai.flow.persistence.base import FlowPersistence
from crewai.flow.persistence.sqlite import SQLiteFlowPersistence

from repoclinic.agents import (
    BranchExecutor,
    CrewBranchExecutor,
    build_failed_architecture_output,
    build_failed_performance_output,
    build_failed_security_output,
    synthesize_roadmap,
)
from repoclinic.config import ModelFactory, load_app_config
from repoclinic.config.models import AppConfig
from repoclinic.flow.state import RepoClinicFlowState
from repoclinic.flow.transition_store import FlowTransitionStore
from repoclinic.schemas.analysis_models import (
    ArchitectureAgentOutput,
    PerformanceAgentOutput,
    SecurityAgentOutput,
)
from repoclinic.schemas.enums import FlowNodeState
from repoclinic.schemas.input_models import AnalyzeRequest
from repoclinic.schemas.scanner_models import ScannerOutput
from repoclinic.scanner.pipeline import ScannerPipeline


class RepoClinicFlow(Flow[RepoClinicFlowState]):
    """Stateful fan-out/fan-in flow with checkpointed persistence."""

    initial_state = RepoClinicFlowState

    def __init__(
        self,
        *,
        config: AppConfig,
        scanner_pipeline: ScannerPipeline,
        transition_store: FlowTransitionStore,
        branch_executor: BranchExecutor,
        persistence: FlowPersistence | None = None,
    ) -> None:
        super().__init__(
            persistence=persistence or SQLiteFlowPersistence(db_path=".sqlite/repoclinic.db"),
            suppress_flow_events=False,
        )
        self.config = config
        self.scanner_pipeline = scanner_pipeline
        self.transition_store = transition_store
        self.branch_executor = branch_executor

    @start()
    def validate_request_and_state(self) -> dict[str, Any]:
        """Validate request/config and initialize flow checkpoint state."""
        if self._node_completed("start"):
            return {"status": "already_completed", "run_id": self.state.run_id}

        if not self.state.request_payload:
            raise ValueError(
                "request_payload is required in flow state before kickoff execution"
            )

        request = AnalyzeRequest.model_validate(self.state.request_payload)
        self.state.schema_version = request.schema_version
        self.state.run_id = request.run_id
        self.state.id = request.run_id
        self.state.provider_profile = (
            self.state.provider_profile or self.config.default_provider_profile
        )
        self._mark_node_transition(
            node_id="start",
            to_state=FlowNodeState.COMPLETED,
            reason="Validated analyze request and provider profile",
        )
        return {"run_id": self.state.run_id}

    @listen(validate_request_and_state)
    def run_scanner_stage(self) -> dict[str, Any]:
        """Execute deterministic scanner stage."""
        if self._node_completed("scanner"):
            return self.state.scanner_output or {}

        self._mark_node_transition(
            node_id="scanner",
            to_state=FlowNodeState.RUNNING,
            reason="Executing scanner stage",
        )
        try:
            request = AnalyzeRequest.model_validate(self.state.request_payload)
            scanner_output = self.scanner_pipeline.run(request)
            self.state.scanner_output = scanner_output.model_dump(mode="json")
            self.state.branch_statuses["scanner"] = "completed"
            self._mark_node_transition(
                node_id="scanner",
                to_state=FlowNodeState.COMPLETED,
                reason="Scanner stage completed",
            )
            return self.state.scanner_output
        except Exception as exc:
            self.state.branch_statuses["scanner"] = "failed"
            self.state.branch_failures["scanner"] = str(exc)
            self._mark_node_transition(
                node_id="scanner",
                to_state=FlowNodeState.FAILED,
                reason=f"Scanner stage failed: {exc}",
            )
            raise

    @listen(run_scanner_stage)
    def run_architecture_branch(self) -> dict[str, Any]:
        """Run architecture branch analysis."""
        if self._node_completed("architecture"):
            return self.state.architecture_output or {}
        self._mark_node_transition(
            node_id="architecture",
            to_state=FlowNodeState.RUNNING,
            reason="Executing architecture branch",
        )
        scanner_output = ScannerOutput.model_validate(self.state.scanner_output or {})
        try:
            output = self.branch_executor.run_architecture(scanner_output)
            self.state.branch_statuses["architecture"] = "completed"
            node_state = FlowNodeState.COMPLETED
            reason = "Architecture branch completed"
        except Exception as exc:
            self.state.branch_statuses["architecture"] = "failed"
            self.state.branch_failures["architecture"] = str(exc)
            output = build_failed_architecture_output(
                run_id=self.state.run_id,
                schema_version=self.state.schema_version,
                reason=str(exc),
            )
            node_state = FlowNodeState.FAILED
            reason = f"Architecture branch failed: {exc}"
        self.state.architecture_output = output.model_dump(mode="json")
        self._mark_node_transition(node_id="architecture", to_state=node_state, reason=reason)
        return self.state.architecture_output

    @listen(run_scanner_stage)
    def run_security_branch(self) -> dict[str, Any]:
        """Run security branch analysis."""
        if self._node_completed("security"):
            return self.state.security_output or {}
        self._mark_node_transition(
            node_id="security",
            to_state=FlowNodeState.RUNNING,
            reason="Executing security branch",
        )
        scanner_output = ScannerOutput.model_validate(self.state.scanner_output or {})
        try:
            output = self.branch_executor.run_security(scanner_output)
            self.state.branch_statuses["security"] = "completed"
            node_state = FlowNodeState.COMPLETED
            reason = "Security branch completed"
        except Exception as exc:
            self.state.branch_statuses["security"] = "failed"
            self.state.branch_failures["security"] = str(exc)
            output = build_failed_security_output(
                run_id=self.state.run_id,
                schema_version=self.state.schema_version,
                reason=str(exc),
            )
            node_state = FlowNodeState.FAILED
            reason = f"Security branch failed: {exc}"
        self.state.security_output = output.model_dump(mode="json")
        self._mark_node_transition(node_id="security", to_state=node_state, reason=reason)
        return self.state.security_output

    @listen(run_scanner_stage)
    def run_performance_branch(self) -> dict[str, Any]:
        """Run performance branch analysis."""
        if self._node_completed("performance"):
            return self.state.performance_output or {}
        self._mark_node_transition(
            node_id="performance",
            to_state=FlowNodeState.RUNNING,
            reason="Executing performance branch",
        )
        scanner_output = ScannerOutput.model_validate(self.state.scanner_output or {})
        try:
            output = self.branch_executor.run_performance(scanner_output)
            self.state.branch_statuses["performance"] = "completed"
            node_state = FlowNodeState.COMPLETED
            reason = "Performance branch completed"
        except Exception as exc:
            self.state.branch_statuses["performance"] = "failed"
            self.state.branch_failures["performance"] = str(exc)
            output = build_failed_performance_output(
                run_id=self.state.run_id,
                schema_version=self.state.schema_version,
                reason=str(exc),
            )
            node_state = FlowNodeState.FAILED
            reason = f"Performance branch failed: {exc}"
        self.state.performance_output = output.model_dump(mode="json")
        self._mark_node_transition(node_id="performance", to_state=node_state, reason=reason)
        return self.state.performance_output

    @listen(and_(run_architecture_branch, run_security_branch, run_performance_branch))
    def run_roadmap_trigger(self) -> dict[str, Any]:
        """Fan-in join and roadmap trigger after all branches finish."""
        if self._node_completed("roadmap"):
            return self.state.roadmap_output or {}

        self._mark_node_transition(
            node_id="roadmap",
            to_state=FlowNodeState.RUNNING,
            reason="Executing roadmap synthesis trigger",
        )
        try:
            architecture_output = ArchitectureAgentOutput.model_validate(
                self.state.architecture_output or {}
            )
            security_output = SecurityAgentOutput.model_validate(self.state.security_output or {})
            performance_output = PerformanceAgentOutput.model_validate(
                self.state.performance_output or {}
            )
            roadmap_items = synthesize_roadmap(
                architecture_output=architecture_output,
                security_output=security_output,
                performance_output=performance_output,
            )
            degraded = any(
                self.state.branch_statuses.get(branch) == "failed"
                for branch in ("architecture", "security", "performance")
            )
            self.state.branch_statuses["roadmap"] = "degraded" if degraded else "completed"
            self.state.roadmap_output = {
                "schema_version": self.state.schema_version,
                "run_id": self.state.run_id,
                "status": self.state.branch_statuses["roadmap"],
                "items": [item.model_dump(mode="json") for item in roadmap_items],
                "branch_failures": dict(self.state.branch_failures),
            }
            self._mark_node_transition(
                node_id="roadmap",
                to_state=FlowNodeState.COMPLETED,
                reason="Roadmap trigger completed",
            )
            return self.state.roadmap_output
        except Exception as exc:
            self.state.branch_statuses["roadmap"] = "failed"
            self.state.branch_failures["roadmap"] = str(exc)
            self._mark_node_transition(
                node_id="roadmap",
                to_state=FlowNodeState.FAILED,
                reason=f"Roadmap trigger failed: {exc}",
            )
            raise

    def _node_completed(self, node_id: str) -> bool:
        return node_id in self.state.completed_nodes

    def _mark_node_transition(
        self,
        *,
        node_id: str,
        to_state: FlowNodeState,
        reason: str,
    ) -> None:
        from_state = self.state.state.value if hasattr(self.state.state, "value") else str(
            self.state.state
        )
        self.state.flow_id = self.flow_id
        self.state.node_id = node_id
        self.state.state = to_state
        self.state.checkpoint_id = f"{self.state.run_id}:{node_id}"
        self.state.resume_token = self.state.id
        if to_state == FlowNodeState.COMPLETED and node_id not in self.state.completed_nodes:
            self.state.completed_nodes.append(node_id)
        self.transition_store.record_transition(
            run_id=self.state.run_id or self.state.id,
            node_id=node_id,
            from_state=from_state,
            to_state=to_state.value,
            reason=reason,
        )
        if self._persistence is not None:
            self._persistence.save_state(
                flow_uuid=self.state.id,
                method_name=node_id,
                state_data=self._copy_and_serialize_state(),
            )


class RepoClinicFlowRunner:
    """Facade for kicking off and resuming RepoClinic flow runs."""

    def __init__(
        self,
        *,
        config_path: Path | None = None,
        db_path: Path | None = None,
        workspace_root: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.config = load_app_config(config_path)
        self.db_path = db_path or Path(".sqlite/repoclinic.db")
        self.workspace_root = workspace_root or Path(".scanner-workspace")
        self.env = env or dict(os.environ)

    def kickoff(
        self,
        *,
        request: AnalyzeRequest,
        provider_profile: str | None = None,
        branch_executor: BranchExecutor | None = None,
    ) -> RepoClinicFlowState:
        """Kick off a new flow run."""
        flow = self._build_flow(provider_profile=provider_profile, branch_executor=branch_executor)
        flow.kickoff(
            inputs={
                "id": request.run_id,
                "run_id": request.run_id,
                "schema_version": request.schema_version,
                "request_payload": request.model_dump(mode="json"),
                "provider_profile": provider_profile or self.config.default_provider_profile,
            }
        )
        return flow.state

    def resume(
        self,
        *,
        run_id: str,
        provider_profile: str | None = None,
        branch_executor: BranchExecutor | None = None,
    ) -> RepoClinicFlowState:
        """Resume an existing run by run_id checkpoint."""
        flow = self._build_flow(provider_profile=provider_profile, branch_executor=branch_executor)
        flow.kickoff(inputs={"id": run_id})
        return flow.state

    def _build_flow(
        self,
        *,
        provider_profile: str | None,
        branch_executor: BranchExecutor | None,
    ) -> RepoClinicFlow:
        scanner_pipeline = ScannerPipeline(
            config=self.config,
            workspace_root=self.workspace_root,
            db_path=self.db_path,
        )
        transition_store = FlowTransitionStore(self.db_path)
        model_factory = ModelFactory(self.config)
        executor = branch_executor or CrewBranchExecutor(
            config=self.config,
            model_factory=model_factory,
            provider_profile=provider_profile or self.config.default_provider_profile,
            env=self.env,
        )
        flow = RepoClinicFlow(
            config=self.config,
            scanner_pipeline=scanner_pipeline,
            transition_store=transition_store,
            branch_executor=executor,
            persistence=SQLiteFlowPersistence(db_path=str(self.db_path)),
        )
        return flow
