"""Enum definitions for canonical contracts."""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class FindingCategory(str, Enum):
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    PERFORMANCE = "performance"


class FindingStatus(str, Enum):
    CONFIRMED = "confirmed"
    SUSPECTED = "suspected"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    FAILED = "failed"


class ProviderType(str, Enum):
    OPENAI = "openai"
    LM_STUDIO = "lm_studio"


class ArchitectureType(str, Enum):
    MONOLITH = "monolith"
    MICROSERVICES = "microservices"
    MODULAR_MONOLITH = "modular_monolith"
    UNKNOWN = "unknown"


class FlowNodeState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


LEGACY_PROVIDER_MAP: dict[str, ProviderType] = {
    "openai": ProviderType.OPENAI,
    "lmstudio": ProviderType.LM_STUDIO,
    "lm-studio": ProviderType.LM_STUDIO,
    "lm_studio": ProviderType.LM_STUDIO,
}


def normalize_provider_type(raw_value: str | ProviderType) -> ProviderType:
    """Normalize provider labels into canonical enum values."""
    if isinstance(raw_value, ProviderType):
        return raw_value
    normalized = LEGACY_PROVIDER_MAP.get(raw_value.strip().lower())
    if normalized is None:
        raise ValueError(f"Unsupported provider type: {raw_value}")
    return normalized
