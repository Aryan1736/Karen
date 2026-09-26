"""
Karen's Ear — Incident-Report Link & Ingest Result Schemas
Adheres strictly to docs/data-schema.md Section 2.4 and docs/api-contract.md Section 3.
"""
from typing import Optional
from pydantic import Field

from backend.app.schemas.common import (
    IsoUtcDatetime,
    KarenBaseModel,
    ProcessingStatus,
    RelationshipType,
)


class IncidentReportLinkResponse(KarenBaseModel):
    """Join record linking a report to an incident."""
    id: str
    incident_id: str
    report_id: str
    relationship_type: RelationshipType
    similarity_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Cosine similarity at fusion time",
    )
    fused_at: IsoUtcDatetime


class ReportIngestResult(KarenBaseModel):
    """Data payload returned on successful report ingestion (201 Created)."""
    report_id: str
    incident_id: str
    is_new_incident: bool
    relationship: RelationshipType
    processing_status: ProcessingStatus
