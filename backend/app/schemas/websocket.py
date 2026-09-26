"""
Karen's Ear — WebSocket Event Schemas & Envelopes
Adheres strictly to docs/api-contract.md Section 6 and architecture/realtime.md Section 4.
"""
from enum import Enum
from typing import Any, Optional
from pydantic import Field

from backend.app.schemas.common import (
    IsoUtcDatetime,
    KarenBaseModel,
)


class WebSocketEventType(str, Enum):
    """Supported real-time WebSocket event types."""
    INCIDENT_CREATED = "INCIDENT_CREATED"
    INCIDENT_UPDATED = "INCIDENT_UPDATED"
    INCIDENT_STATUS_CHANGED = "INCIDENT_STATUS_CHANGED"
    SIMULATION_PULSE = "SIMULATION_PULSE"
    PING = "PING"


class WebSocketEnvelope(KarenBaseModel):
    """
    Canonical server -> client real-time event envelope.
    MUST have exactly: event, payload, timestamp.
    No top-level 'type' field.
    """
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: IsoUtcDatetime


class IncidentStatusChangedPayload(KarenBaseModel):
    """Payload for INCIDENT_STATUS_CHANGED event."""
    incident_id: str
    old_status: str
    new_status: str


class SimulationPulsePayload(KarenBaseModel):
    """Payload for SIMULATION_PULSE event."""
    injected_count: int = Field(ge=0, description="Count of reports injected in this pulse")
    total_simulated: int = Field(ge=0, description="Total reports simulated so far in this run")
    scenario: str = Field(min_length=1, description="Scenario template identifier")


class PingPayload(KarenBaseModel):
    """Payload for server PING heartbeat (empty object)."""
    pass


class ClientPongMessage(KarenBaseModel):
    """Client keepalive PONG message format."""
    type: Optional[str] = None
    event: Optional[str] = None
