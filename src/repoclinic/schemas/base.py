"""Shared schema base classes."""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class StrictSchemaModel(BaseModel):
    """Base model with strict validation defaults."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, frozen=False)


class VersionedRunModel(StrictSchemaModel):
    """Model envelope for versioned run-scoped payloads."""

    schema_version: str = Field(min_length=1)
    run_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
