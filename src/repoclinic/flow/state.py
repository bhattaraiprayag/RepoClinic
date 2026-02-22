"""Flow state model for scanner-first orchestration."""

from __future__ import annotations

from typing import Any

from crewai.flow.flow import FlowState
from pydantic import Field

from repoclinic.constants import SCHEMA_VERSION
from repoclinic.schemas.enums import FlowNodeState


class RepoClinicFlowState(FlowState):
    """State payload persisted by CrewAI flow persistence."""

    schema_version: str = SCHEMA_VERSION
    run_id: str = ""
    request_payload: dict[str, Any] = Field(default_factory=dict)
    provider_profile: str | None = None
    flow_id: str = "repoclinic-flow"
    node_id: str = "start"
    state: FlowNodeState = FlowNodeState.PENDING
    resume_token: str | None = None
    checkpoint_id: str | None = None
    completed_nodes: list[str] = Field(default_factory=list)
    branch_statuses: dict[str, str] = Field(
        default_factory=lambda: {
            "scanner": "pending",
            "architecture": "pending",
            "security": "pending",
            "performance": "pending",
            "roadmap": "pending",
        }
    )
    branch_failures: dict[str, str] = Field(default_factory=dict)
    run_manifest: dict[str, Any] | None = None
    scanner_output: dict[str, Any] | None = None
    architecture_output: dict[str, Any] | None = None
    security_output: dict[str, Any] | None = None
    performance_output: dict[str, Any] | None = None
    roadmap_output: dict[str, Any] | None = None
