"""
Karen's Ear — Incident Canonical Schemas
Adheres strictly to docs/data-schema.md Section 2.3 and docs/api-contract.md Section 5.
"""
from typing import Any, Optional, Union
from pydantic import Field, field_validator

from backend.app.schemas.audit import AuditLogResponse
from backend.app.schemas.common import (
    IncidentStatus,
    IncidentType,
    IsoUtcDatetime,
    KarenBaseModel,
    LocationPrecision,
    PriorityLevel,
    UrgencyLevel,
)
from backend.app.schemas.report import RawReportResponse


class IncidentLocation(KarenBaseModel):
    """Tactical location details for an incident."""
    text: Optional[str] = Field(default=None, description="Primary location phrasing")
    latitude: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Geocoded latitude; null if unverified without hallucination",
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Geocoded longitude; null if unverified without hallucination",
    )
    precision: LocationPrecision = Field(
        default=LocationPrecision.UNKNOWN,
        description="Coordinate precision",
    )


class IncidentRisk(KarenBaseModel):
    """Current assessed victims count."""
    count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Assessed casualties or trapped individuals count",
    )


class Corroboration(KarenBaseModel):
    """Corroboration metrics and explanation."""
    report_count: int = Field(default=1, ge=1, description="Total reports linked to incident")
    independent_source_count: int = Field(
        default=1,
        ge=1,
        description="Distinct eyewitness or source count",
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Saturating corroboration metric",
    )
    explanation: str = Field(..., description="Plain-language corroboration summary")


class ConfidenceBlock(KarenBaseModel):
    """Overall and component model confidences."""
    overall: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall model confidence",
    )
    components: dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="Component confidence breakdown",
    )


class PriorityFactor(KarenBaseModel):
    """Individual factor contribution in priority calculation."""
    factor: str = Field(..., description="Factor label (e.g. 'Urgency', 'People at Risk')")
    value: Union[int, float, str] = Field(..., description="Observed factor value")
    weight: float = Field(..., description="Configured weight for this dimension")
    contribution: float = Field(..., description="Calculated point contribution")


class PriorityBlock(KarenBaseModel):
    """Deterministic priority score and factor breakdown."""
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Ranked sorting metric [0.0, 100.0]",
    )
    level: PriorityLevel = Field(..., description="Priority tier")
    explanation: str = Field(..., description="Human-readable justification")
    factors: list[PriorityFactor] = Field(
        default_factory=list,
        description="Array of component factor contributions",
    )


class HumanOverrideBlock(KarenBaseModel):
    """Active operator override snapshot."""
    active: bool = Field(default=False, description="True if operator overrode any field")
    updated_by: Optional[str] = Field(default=None, description="Operator identifier")
    updated_at: Optional[str] = Field(default=None, description="ISO-8601 timestamp of override")
    reason: Optional[str] = Field(default=None, description="Mandatory justification")


class IncidentResponse(KarenBaseModel):
    """
    Canonical operational Incident entity returned by GET /incidents and GET /incidents/{id}.
    Matches docs/data-schema.md Section 2.3 and docs/api-contract.md Section 5.1.
    """
    incident_id: str
    status: IncidentStatus
    incident_type: Optional[IncidentType] = None
    urgency: Optional[UrgencyLevel] = None
    location: IncidentLocation
    people_at_risk: IncidentRisk
    required_response: list[str] = Field(default_factory=list)
    source_report_ids: list[str] = Field(default_factory=list)
    corroboration: Corroboration
    ml_confidence: ConfidenceBlock
    priority: PriorityBlock
    human_override: HumanOverrideBlock
    is_synthetic: bool = False
    created_at: IsoUtcDatetime
    updated_at: IsoUtcDatetime


class IncidentReviewRequest(KarenBaseModel):
    """Payload for POST /incidents/{id}/review to transition incident state."""
    operator_id: Optional[str] = Field(default=None, description="Acting operator identifier (optional if X-Operator-Id header provided)")
    target_status: IncidentStatus = Field(..., description="Target status transition")
    notes: str = Field(..., description="Review notes (at least 5 non-whitespace characters)")

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str) -> str:
        if not v or len(v.strip()) < 5:
            raise ValueError("Review notes must contain at least 5 non-whitespace characters.")
        return v.strip()


class IncidentOverrideRequest(KarenBaseModel):
    """Payload for POST /incidents/{id}/override with mandatory justification."""
    operator_id: Optional[str] = Field(default=None, description="Acting operator identifier (optional if X-Operator-Id header provided)")
    field: str = Field(..., min_length=1, description="Field to override (e.g. urgency, priority_score)")
    new_value: Any = Field(..., description="New value assigned by operator")
    reason: str = Field(
        ...,
        description="Mandatory justification (at least 5 non-whitespace characters)",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v or len(v.strip()) < 5:
            raise ValueError("Override reason must contain at least 5 non-whitespace characters.")
        return v.strip()


class IncidentListResponse(KarenBaseModel):
    """Paginated collection returned by GET /incidents."""
    incidents: list[IncidentResponse]
    total_count: int
    critical_count: int


class IncidentDetailResponse(KarenBaseModel):
    """Deep incident inspection response for GET /incidents/{id}."""
    incident: IncidentResponse
    source_reports: list[RawReportResponse] = Field(default_factory=list)
    audit_trail: list[AuditLogResponse] = Field(default_factory=list)


class TimelineEvent(KarenBaseModel):
    """Standardized chronological event item for GET /incidents/{id}/timeline."""
    event_id: str
    event_type: str
    timestamp: IsoUtcDatetime
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class IncidentTimelineResponse(KarenBaseModel):
    """Timeline response collection for GET /incidents/{id}/timeline."""
    incident_id: str
    total_events: int
    events: list[TimelineEvent] = Field(default_factory=list)
