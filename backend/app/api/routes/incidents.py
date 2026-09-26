"""
Karen's Ear — Incident REST API Routes
Implements:
1. GET /incidents
2. GET /incidents/{id}
3. POST /incidents/{id}/review
4. POST /incidents/{id}/override
5. GET /incidents/{id}/timeline
Adheres strictly to docs/api-contract.md Section 5 and gemini.md Section 6.6.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status as http_status
from sqlalchemy.orm import Session

from backend.app.core.envelope import get_request_id, success_response
from backend.app.db.session import get_db
from backend.app.schemas.incident import (
    IncidentOverrideRequest,
    IncidentReviewRequest,
)
from backend.app.services.incident_service import IncidentService
from backend.app.services.websocket_manager import broadcast_event

logger = logging.getLogger("karen.backend.api.incidents")

router = APIRouter(tags=["Incidents"])


def get_current_incident_service(db: Session = Depends(get_db)) -> IncidentService:
    """Dependency provider for IncidentService."""
    return IncidentService(db=db)


@router.get(
    "/incidents",
    status_code=http_status.HTTP_200_OK,
    summary="List Incidents",
    description="Powers the Command Center priority queue and map view with optional status/level filtering and pagination.",
)
def list_incidents(
    request: Request,
    status: Optional[str] = Query(
        default=None,
        description="Optional comma-separated status filter (e.g. ACTIVE,NEEDS_REVIEW,VERIFIED)",
    ),
    level: Optional[str] = Query(
        default=None,
        description="Optional comma-separated priority level filter (e.g. CRITICAL,HIGH)",
    ),
    limit: int = Query(default=50, description="Max records to return [1, 200]"),
    offset: int = Query(default=0, description="Offset for pagination >= 0"),
    service: IncidentService = Depends(get_current_incident_service),
) -> Response:
    """
    List incidents ordered by priority_score DESC, updated_at DESC.
    If status is omitted -> return all statuses.
    If level is omitted -> return all levels.
    """
    req_id = getattr(request.state, "request_id", None) or get_request_id()

    result = service.get_incidents(
        status_filter=status,
        level_filter=level,
        limit=limit,
        offset=offset,
    )

    return success_response(
        data=result.model_dump(mode="json"),
        status_code=http_status.HTTP_200_OK,
        request_id=req_id,
    )


@router.get(
    "/incidents/{id}",
    status_code=http_status.HTTP_200_OK,
    summary="Get Deep Incident Details",
    description="Fetches deep tactical details for an incident, including linked source reports and human audit trail.",
)
def get_incident_detail(
    id: str,
    request: Request,
    service: IncidentService = Depends(get_current_incident_service),
) -> Response:
    """
    Returns canonical Incident, linked RawReports, and AuditLog trail.
    Raises 404 if incident does not exist.
    """
    req_id = getattr(request.state, "request_id", None) or get_request_id()

    detail = service.get_incident_detail(incident_id=id)

    return success_response(
        data=detail.model_dump(mode="json"),
        status_code=http_status.HTTP_200_OK,
        request_id=req_id,
    )


@router.post(
    "/incidents/{id}/review",
    status_code=http_status.HTTP_200_OK,
    summary="Review Incident Status",
    description="Transitions incident status with operator attribution, mandatory review notes, and priority recalculation.",
)
def review_incident(
    id: str,
    payload: IncidentReviewRequest,
    request: Request,
    x_operator_id: Optional[str] = Header(default=None, alias="X-Operator-Id"),
    service: IncidentService = Depends(get_current_incident_service),
) -> Response:
    """
    Execute an operator review state transition:
    - Enforces state machine rules
    - Resolves operator identity between header and body
    - Logs audit record
    - Recalculates priority on status change
    - Post-commit: broadcasts 1. INCIDENT_STATUS_CHANGED, 2. INCIDENT_UPDATED
    """
    req_id = getattr(request.state, "request_id", None) or get_request_id()

    incident_dto, audit_dto = service.review_incident(
        incident_id=id,
        target_status=payload.target_status,
        notes=payload.notes,
        x_operator_id=x_operator_id,
        body_operator_id=payload.operator_id,
    )

    # Post-commit real-time event broadcasts (safe and non-blocking to REST)
    try:
        status_changed_payload = {
            "incident_id": incident_dto.incident_id,
            "old_status": str(audit_dto.previous_value),
            "new_status": str(audit_dto.new_value),
        }
        broadcast_event("INCIDENT_STATUS_CHANGED", status_changed_payload)
        broadcast_event("INCIDENT_UPDATED", incident_dto.model_dump(mode="json"))
    except Exception as broadcast_exc:
        logger.error(
            "Failed to dispatch post-commit WebSocket broadcast for review on %s: %s",
            incident_dto.incident_id,
            type(broadcast_exc).__name__,
        )

    return success_response(
        data={
            "incident": incident_dto.model_dump(mode="json"),
            "audit": audit_dto.model_dump(mode="json"),
        },
        status_code=http_status.HTTP_200_OK,
        request_id=req_id,
    )


@router.post(
    "/incidents/{id}/override",
    status_code=http_status.HTTP_200_OK,
    summary="Override Incident Field",
    description="Overrides an operator-controlled incident field with mandatory reason (>= 5 chars), audit logging, and human override snapshot update.",
)
def override_incident(
    id: str,
    payload: IncidentOverrideRequest,
    request: Request,
    x_operator_id: Optional[str] = Header(default=None, alias="X-Operator-Id"),
    service: IncidentService = Depends(get_current_incident_service),
) -> Response:
    """
    Execute an operator field override:
    - Allowed fields: urgency, incident_type, people_at_risk_count, location, required_response, priority_score
    - Updates human_override snapshot
    - Protects against subsequent ML automation
    - Recalculates priority when applicable
    - Post-commit: broadcasts INCIDENT_UPDATED with complete canonical IncidentResponse
    """
    req_id = getattr(request.state, "request_id", None) or get_request_id()

    incident_dto, audit_dto = service.override_incident(
        incident_id=id,
        field=payload.field,
        new_value=payload.new_value,
        reason=payload.reason,
        x_operator_id=x_operator_id,
        body_operator_id=payload.operator_id,
    )

    # Post-commit real-time event broadcast (safe and non-blocking to REST)
    try:
        broadcast_event("INCIDENT_UPDATED", incident_dto.model_dump(mode="json"))
    except Exception as broadcast_exc:
        logger.error(
            "Failed to dispatch post-commit WebSocket broadcast for override on %s: %s",
            incident_dto.incident_id,
            type(broadcast_exc).__name__,
        )

    return success_response(
        data={
            "incident": incident_dto.model_dump(mode="json"),
            "audit": audit_dto.model_dump(mode="json"),
        },
        status_code=http_status.HTTP_200_OK,
        request_id=req_id,
    )



@router.get(
    "/incidents/{id}/timeline",
    status_code=http_status.HTTP_200_OK,
    summary="Get Incident Event Timeline",
    description="Synthesizes chronological event audit trail from report fusion events, priority calculations, and operator actions.",
)
def get_incident_timeline(
    id: str,
    request: Request,
    order: str = Query(default="asc", description="Sort order: 'asc' or 'desc'"),
    service: IncidentService = Depends(get_current_incident_service),
) -> Response:
    """
    Synthesize chronological timeline for an incident from existing database persistence.
    """
    req_id = getattr(request.state, "request_id", None) or get_request_id()

    timeline = service.get_incident_timeline(
        incident_id=id,
        order=order,
    )

    return success_response(
        data=timeline.model_dump(mode="json"),
        status_code=http_status.HTTP_200_OK,
        request_id=req_id,
    )
