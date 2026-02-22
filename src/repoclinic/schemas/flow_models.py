"""ARC-FL2 flow-state schema contracts."""

from __future__ import annotations

from pydantic import Field

from repoclinic.schemas.base import StrictSchemaModel
from repoclinic.schemas.enums import FlowNodeState


class FlowState(StrictSchemaModel):
    """Flow checkpoint state fields for ARC-FL2."""

    flow_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    state: FlowNodeState
    resume_token: str | None = None
