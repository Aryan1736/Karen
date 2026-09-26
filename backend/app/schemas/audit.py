"""
Karen's Ear — Audit Log Schema
Adheres strictly to docs/data-schema.md Section 2.5 and gemini.md Section 6.5.
"""
from typing import Any
from pydantic import Field

from backend.app.schemas.common import IsoUtcDatetime, KarenBaseModel


class AuditLogResponse(KarenBaseModel):
    """Immutable audit record for operator overrides and state transitions."""
    override_id: str
    incident_id: str
    operator_id: str
    field: str
    previous_value: Any = None
    new_value: Any = None
    reason: str = Field(..., min_length=5, description="Mandatory justification string (>= 5 chars)")
    created_at: IsoUtcDatetime
