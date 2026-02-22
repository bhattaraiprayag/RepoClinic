"""Input and run metadata schema contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from repoclinic.schemas.base import StrictSchemaModel, VersionedRunModel
from repoclinic.schemas.enums import ProviderType, normalize_provider_type


class AnalyzeInput(StrictSchemaModel):
    """Input source contract for analysis."""

    source_type: Literal["github_url", "local_path"]
    github_url: str | None = None
    local_path: str | None = None
    branch: str | None = None
    commit: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "AnalyzeInput":
        if self.source_type == "github_url" and not self.github_url:
            raise ValueError("github_url is required when source_type=github_url")
        if self.source_type == "local_path" and not self.local_path:
            raise ValueError("local_path is required when source_type=local_path")
        return self


class ProviderConfig(StrictSchemaModel):
    """Provider runtime configuration."""

    type: ProviderType
    model: str = Field(min_length=1)
    temperature: float = 0.1
    seed: int = 42
    max_tokens: int = Field(default=4096, gt=0)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_provider(cls, value: str | ProviderType) -> ProviderType:
        return normalize_provider_type(value)


class TimeoutConfig(StrictSchemaModel):
    """Timeout profile for scanner and agent stages."""

    scanner_seconds: int = Field(default=900, gt=0)
    agent_seconds: int = Field(default=600, gt=0)


class FeatureFlags(StrictSchemaModel):
    """Feature toggles for deterministic tool runs."""

    enable_tree_sitter: bool = True
    enable_bandit: bool = True
    enable_semgrep: bool = True
    enable_osv: bool = True


class ExecutionConfig(StrictSchemaModel):
    """Execution settings for a run."""

    provider: ProviderConfig
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags)


class AnalyzeRequest(VersionedRunModel):
    """Top-level analysis request schema."""

    input: AnalyzeInput
    execution: ExecutionConfig


class RepoMetadata(StrictSchemaModel):
    """Repository metadata captured per run."""

    repo_name: str = Field(min_length=1)
    resolved_path: str = Field(min_length=1)
    git_commit_sha: str | None = None


class ToolVersions(StrictSchemaModel):
    """Tool version fingerprinting for reproducibility."""

    crewai: str = Field(min_length=1)
    python: str = Field(min_length=1)
    semgrep: str | None = None
    bandit: str | None = None
    osv_scanner: str | None = None
    ripgrep: str | None = None


class PromptVersions(StrictSchemaModel):
    """Prompt/template version references."""

    scanner: str = Field(min_length=1)
    architecture: str = Field(min_length=1)
    security: str = Field(min_length=1)
    performance: str = Field(min_length=1)
    roadmap: str = Field(min_length=1)


class RunMetadata(VersionedRunModel):
    """Run metadata envelope."""

    repo: RepoMetadata
    tool_versions: ToolVersions
    prompt_versions: PromptVersions
