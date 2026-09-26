"""
Karen's Ear — Simulation Run Schemas
Adheres strictly to docs/data-schema.md Section 2.6 and docs/api-contract.md Section 5.6.
"""
from typing import Optional
from pydantic import Field

from backend.app.schemas.common import (
    IsoUtcDatetime,
    KarenBaseModel,
    SimulationStatus,
)


class SimulationRunResponse(KarenBaseModel):
    """Metadata for a disaster simulation playback run."""
    simulation_id: str
    scenario_id: str
    status: SimulationStatus
    reports_injected: int = Field(default=0, ge=0)
    started_at: IsoUtcDatetime
    ended_at: Optional[IsoUtcDatetime] = None


class SimulationStartRequest(KarenBaseModel):
    """Configuration to start a simulated emergency scenario."""
    scenario_id: str = Field(..., min_length=1, description="Scenario template identifier")
    rate_per_minute: int = Field(default=15, ge=1, le=1000, description="Report injection rate")
    total_reports: int = Field(default=30, ge=1, le=10000, description="Total reports to inject")
    duplicate_probability: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Probability of synthetic duplicates",
    )
