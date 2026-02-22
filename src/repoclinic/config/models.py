"""Pydantic models for central YAML configuration."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from repoclinic.constants import SCHEMA_VERSION
from repoclinic.schemas.base import StrictSchemaModel
from repoclinic.schemas.enums import ProviderType, normalize_provider_type


class RetryConfig(StrictSchemaModel):
    """Retry controls for provider calls."""

    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_seconds: float = Field(default=1.0, ge=0.0)
    jitter_seconds: float = Field(default=0.2, ge=0.0, le=5.0)


class ProviderCapabilities(StrictSchemaModel):
    """Capabilities metadata for a provider profile."""

    context_window: int = Field(gt=0)
    supports_structured_output: bool = True
    retries: int = Field(default=3, ge=1, le=10)


class ProviderProfile(StrictSchemaModel):
    """Provider profile definition."""

    provider_type: ProviderType
    model: str = Field(min_length=1)
    api_key_env: str | None = None
    base_url: str | None = None
    temperature: float = 0.1
    seed: int = 42
    max_tokens: int = Field(default=4096, gt=0)
    timeout_seconds: int = Field(default=600, gt=0)
    capabilities: ProviderCapabilities

    @field_validator("provider_type", mode="before")
    @classmethod
    def normalize_provider(cls, value: str | ProviderType) -> ProviderType:
        return normalize_provider_type(value)

    @model_validator(mode="after")
    def validate_provider_requirements(self) -> "ProviderProfile":
        if self.provider_type == ProviderType.OPENAI and not self.api_key_env:
            raise ValueError("OpenAI profiles must define api_key_env")
        if self.provider_type == ProviderType.LM_STUDIO:
            if not self.base_url:
                raise ValueError("LM Studio profiles must define base_url")
            if not self.api_key_env:
                raise ValueError("LM Studio profiles must define api_key_env")
        if self.max_tokens > self.capabilities.context_window:
            raise ValueError("max_tokens cannot exceed provider context_window")
        return self


class FeatureFlagsConfig(StrictSchemaModel):
    """Deterministic scanner and tool feature flags."""

    enable_tree_sitter: bool = True
    enable_bandit: bool = True
    enable_semgrep: bool = True
    enable_osv: bool = True


class TokenBudgetConfig(StrictSchemaModel):
    """Per-stage token budgets."""

    scanner_context: int = Field(default=8000, gt=0)
    architecture_context: int = Field(default=6000, gt=0)
    security_context: int = Field(default=6000, gt=0)
    performance_context: int = Field(default=6000, gt=0)
    roadmap_context: int = Field(default=6000, gt=0)


class ScanPolicyConfig(StrictSchemaModel):
    """Include/exclude policies for scanner inventory."""

    include_globs: list[str] = Field(default_factory=lambda: ["**/*"])
    exclude_globs: list[str] = Field(
        default_factory=lambda: [
            ".git/**",
            "node_modules/**",
            "dist/**",
            "build/**",
            ".venv/**",
            "__pycache__/**",
            "vendor/**",
        ]
    )
    max_file_size_bytes: int = Field(default=1_000_000, gt=0)
    max_files: int = Field(default=25_000, gt=0)


class TimeoutConfig(StrictSchemaModel):
    """Scanner and agent timeout profile."""

    scanner_seconds: int = Field(default=900, gt=0)
    agent_seconds: int = Field(default=600, gt=0)


class AppConfig(StrictSchemaModel):
    """Central application configuration."""

    schema_version: str = Field(default=SCHEMA_VERSION, min_length=1)
    default_provider_profile: str = Field(min_length=1)
    provider_profiles: dict[str, ProviderProfile]
    retries: RetryConfig = Field(default_factory=RetryConfig)
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)
    token_budgets: TokenBudgetConfig = Field(default_factory=TokenBudgetConfig)
    feature_flags: FeatureFlagsConfig = Field(default_factory=FeatureFlagsConfig)
    scan_policy: ScanPolicyConfig = Field(default_factory=ScanPolicyConfig)

    @model_validator(mode="after")
    def validate_default_profile(self) -> "AppConfig":
        if self.default_provider_profile not in self.provider_profiles:
            raise ValueError("default_provider_profile must exist in provider_profiles")
        return self
