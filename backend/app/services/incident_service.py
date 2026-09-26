"""
Karen's Ear — Incident Service
Business logic layer for incident inspection, review state transitions, field overrides,
and timeline synthesis.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.app.core.envelope import format_utc_now
from backend.app.core.exceptions import AppException, ResourceNotFoundException, ValidationException
from backend.app.engine.correlation import generate_corroboration_explanation
from backend.app.engine.priority import calculate_priority, map_priority_level
from backend.app.models.incident import Incident
from backend.app.repositories.incident_repo import IncidentRepository
from backend.app.schemas.audit import AuditLogResponse
from backend.app.schemas.common import (
    IncidentStatus,
    IncidentType,
    LocationPrecision,
    PriorityLevel,
    ResponseCapability,
    UrgencyLevel,
)
from backend.app.schemas.incident import (
    ConfidenceBlock,
    Corroboration,
    HumanOverrideBlock,
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentLocation,
    IncidentResponse,
    IncidentRisk,
    IncidentTimelineResponse,
    PriorityBlock,
    PriorityFactor,
    TimelineEvent,
)
from backend.app.schemas.report import RawReportResponse

logger = logging.getLogger("karen.backend.service.incident")

CANONICAL_RESPONSE_ORDER: list[str] = [
    ResponseCapability.SEARCH_AND_RESCUE.value,
    ResponseCapability.MEDICAL_EMS.value,
    ResponseCapability.FIRE_HAZMAT.value,
    ResponseCapability.POLICE_SECURITY.value,
    ResponseCapability.PUBLIC_WORKS_UTILITY.value,
]

ALLOWED_OVERRIDE_FIELDS: set[str] = {
    "urgency",
    "incident_type",
    "people_at_risk_count",
    "location",
    "required_response",
    "priority_score",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "ACTIVE": {"VERIFIED", "ESCALATED", "NEEDS_REVIEW", "RESOLVED", "FALSE_REPORT"},
    "NEEDS_REVIEW": {"ACTIVE", "VERIFIED", "ESCALATED", "RESOLVED", "FALSE_REPORT"},
    "VERIFIED": {"ACTIVE", "ESCALATED", "RESOLVED", "FALSE_REPORT"},
    "ESCALATED": {"ACTIVE", "VERIFIED", "RESOLVED"},
    "RESOLVED": {"ACTIVE", "NEEDS_REVIEW"},
    "FALSE_REPORT": set(),
    "NEW": set(),
    "ANALYZING": set(),
}


def resolve_operator_id(x_operator_id: Optional[str], body_operator_id: Optional[str]) -> str:
    """
    Resolve operator identity with explicit precedence and conflict detection:
    - X-Operator-Id header is preferred
    - request body operator_id is fallback
    - if both are present and equal -> accept
    - if only one is present -> use it
    - if neither is present/non-empty -> 422
    - if both are present but DIFFER -> reject with canonical 422 (code = "OPERATOR_ID_MISMATCH")
    """
    h = x_operator_id.strip() if x_operator_id and x_operator_id.strip() else None
    b = body_operator_id.strip() if body_operator_id and body_operator_id.strip() else None

    if h and b:
        if h != b:
            raise AppException(
                code="OPERATOR_ID_MISMATCH",
                message=f"Operator identity in X-Operator-Id header ('{h}') does not match body operator_id ('{b}').",
                status_code=422,
                details=[{"field": "operator_id", "issue": "Header and body operator identities conflict"}],
            )
        return h
    if h:
        return h
    if b:
        return b
    raise ValidationException(
        message="Operator identity must be provided via X-Operator-Id header or operator_id body field.",
        details=[{"field": "operator_id", "issue": "Missing operator identifier"}],
    )


class IncidentService:
    """Service handling incident queries, review transitions, overrides, and timelines."""

    def __init__(
        self,
        db: Session,
        repository: Optional[IncidentRepository] = None,
    ) -> None:
        self.db = db
        self.repo = repository or IncidentRepository()

    def assemble_incident_responses(
        self,
        incidents: list[Incident],
    ) -> list[IncidentResponse]:
        """
        Assemble canonical IncidentResponse objects for a batch of ORM Incident records.
        Executes batched queries to prevent N+1 performance degradation.
        """
        if not incidents:
            return []

        incident_ids = [inc.incident_id for inc in incidents]

        # Batch 1: source report IDs in fusion order
        source_report_ids_map = self.repo.get_source_report_ids_for_incidents(self.db, incident_ids)

        # Batch 2: latest priority calculations
        priority_calc_map = self.repo.get_latest_priority_calculations_for_incidents(self.db, incident_ids)

        # Batch 3: latest linked ML predictions
        ml_pred_map = self.repo.get_latest_ml_predictions_for_incidents(self.db, incident_ids)

        results: list[IncidentResponse] = []
        for inc in incidents:
            source_ids = source_report_ids_map.get(inc.incident_id, [])

            # Corroboration explanation generated deterministically
            corrob_exp = generate_corroboration_explanation(
                inc.report_count,
                inc.independent_source_count,
                float(inc.corroboration_score),
            )
            corroboration = Corroboration(
                report_count=inc.report_count,
                independent_source_count=inc.independent_source_count,
                score=float(inc.corroboration_score),
                explanation=corrob_exp,
            )

            # ML confidence from latest linked prediction
            ml_pred = ml_pred_map.get(inc.incident_id)
            if ml_pred:
                overall_conf = float(ml_pred.overall_confidence) if ml_pred.overall_confidence is not None else None
                components: dict[str, Optional[float]] = {}
                if isinstance(ml_pred.incident_type, dict) and ml_pred.incident_type.get("confidence") is not None:
                    components["incident_type"] = ml_pred.incident_type["confidence"]
                if isinstance(ml_pred.urgency, dict) and ml_pred.urgency.get("confidence") is not None:
                    components["urgency"] = ml_pred.urgency["confidence"]
                if isinstance(ml_pred.location, dict) and ml_pred.location.get("confidence") is not None:
                    components["location"] = ml_pred.location["confidence"]
                ml_conf = ConfidenceBlock(overall=overall_conf, components=components)
            else:
                ml_conf = ConfidenceBlock(overall=None, components={})

            # Priority block from latest calculation or safe defaults
            p_calc = priority_calc_map.get(inc.incident_id)
            if p_calc:
                factors = [PriorityFactor(**f) for f in (p_calc.factors or [])]
                priority_exp = p_calc.explanation
            else:
                factors = []
                priority_exp = "No priority calculation history recorded."

            priority_block = PriorityBlock(
                score=float(inc.priority_score),
                level=PriorityLevel(inc.priority_level),
                explanation=priority_exp,
                factors=factors,
            )

            # Human override snapshot
            ho = inc.human_override or {"active": False}
            override_block = HumanOverrideBlock(
                active=ho.get("active", False),
                updated_by=ho.get("updated_by"),
                updated_at=ho.get("updated_at"),
                reason=ho.get("reason"),
            )

            location_block = IncidentLocation(
                text=inc.location_text,
                latitude=inc.latitude,
                longitude=inc.longitude,
                precision=LocationPrecision(inc.location_precision or "unknown"),
            )

            results.append(
                IncidentResponse(
                    incident_id=inc.incident_id,
                    status=IncidentStatus(inc.status),
                    incident_type=IncidentType(inc.incident_type) if inc.incident_type else None,
                    urgency=UrgencyLevel(inc.urgency) if inc.urgency else None,
                    location=location_block,
                    people_at_risk=IncidentRisk(count=inc.people_at_risk_count),
                    required_response=list(inc.required_response or []),
                    source_report_ids=source_ids,
                    corroboration=corroboration,
                    ml_confidence=ml_conf,
                    priority=priority_block,
                    human_override=override_block,
                    is_synthetic=inc.is_synthetic,
                    created_at=inc.created_at,
                    updated_at=inc.updated_at,
                )
            )

        return results

    def assemble_single_incident(self, incident: Incident) -> IncidentResponse:
        """Helper to assemble a single IncidentResponse object."""
        return self.assemble_incident_responses([incident])[0]

    def get_incidents(
        self,
        status_filter: Optional[str] = None,
        level_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> IncidentListResponse:
        """
        Query incidents with optional status and priority-level filtering and pagination.
        - If status is omitted: return all statuses.
        - If level is omitted: return all priority levels.
        - total_count: count matching current filters before pagination.
        - critical_count: count of CRITICAL incidents matching the exact same filters before pagination.
        """
        if limit < 1 or limit > 200:
            raise ValidationException(
                message=f"Query parameter 'limit' must be between 1 and 200 (received {limit}).",
                details=[{"field": "limit", "issue": "Limit out of bounds [1, 200]"}],
            )
        if offset < 0:
            raise ValidationException(
                message=f"Query parameter 'offset' must be non-negative (received {offset}).",
                details=[{"field": "offset", "issue": "Offset must be >= 0"}],
            )

        # Parse and validate statuses
        statuses: Optional[list[str]] = None
        if status_filter is not None and status_filter.strip():
            raw_statuses = [s.strip().upper() for s in status_filter.split(",") if s.strip()]
            valid_statuses = {s.value for s in IncidentStatus}
            for s in raw_statuses:
                if s not in valid_statuses:
                    raise ValidationException(
                        message=f"Invalid status filter value '{s}'. Allowed: {', '.join(sorted(valid_statuses))}",
                        details=[{"field": "status", "issue": f"Unrecognized status '{s}'"}],
                    )
            statuses = raw_statuses

        # Parse and validate priority levels
        levels: Optional[list[str]] = None
        if level_filter is not None and level_filter.strip():
            raw_levels = [l.strip().upper() for l in level_filter.split(",") if l.strip()]
            valid_levels = {l.value for l in PriorityLevel}
            for l in raw_levels:
                if l not in valid_levels:
                    raise ValidationException(
                        message=f"Invalid level filter value '{l}'. Allowed: {', '.join(sorted(valid_levels))}",
                        details=[{"field": "level", "issue": f"Unrecognized priority level '{l}'"}],
                    )
            levels = raw_levels

        incidents, total_count, critical_count = self.repo.get_incidents(
            self.db,
            statuses=statuses,
            levels=levels,
            limit=limit,
            offset=offset,
        )

        dtos = self.assemble_incident_responses(incidents)

        return IncidentListResponse(
            incidents=dtos,
            total_count=total_count,
            critical_count=critical_count,
        )

    def get_incident_detail(self, incident_id: str) -> IncidentDetailResponse:
        """
        Fetch deep incident details: canonical Incident, linked RawReports, and AuditLog trail.
        Raises ResourceNotFoundException if incident does not exist.
        """
        incident = self.repo.get_incident(self.db, incident_id)
        if not incident:
            raise ResourceNotFoundException(f"Incident '{incident_id}' not found")

        incident_dto = self.assemble_single_incident(incident)

        raw_reports = self.repo.get_incident_source_reports(self.db, incident_id)
        report_dtos = [
            RawReportResponse.model_validate(r) for r in raw_reports
        ]

        audits = self.repo.get_incident_audit_trail(self.db, incident_id)
        audit_dtos = [
            AuditLogResponse.model_validate(a) for a in audits
        ]

        return IncidentDetailResponse(
            incident=incident_dto,
            source_reports=report_dtos,
            audit_trail=audit_dtos,
        )

    def review_incident(
        self,
        incident_id: str,
        target_status: IncidentStatus,
        notes: str,
        x_operator_id: Optional[str] = None,
        body_operator_id: Optional[str] = None,
    ) -> tuple[IncidentResponse, AuditLogResponse]:
        """
        Transition incident status under atomic lock, write audit log, recalculate priority,
        and record historical calculation ledger.
        """
        operator_id = resolve_operator_id(x_operator_id, body_operator_id)

        target_val = target_status.value

        # Atomic lock
        incident = self.repo.get_incident_for_update(self.db, incident_id)
        if not incident:
            raise ResourceNotFoundException(f"Incident '{incident_id}' not found")

        current_status = incident.status

        # Validate transitions
        if target_val in ("NEW", "ANALYZING"):
            raise ValidationException(
                message=f"Transition to pipeline-internal status '{target_val}' is not permitted.",
                details=[{"field": "target_status", "issue": "Internal state is not an operator review target"}],
            )

        if current_status == target_val:
            raise ValidationException(
                message=f"Incident is already in status '{current_status}'.",
                details=[{"field": "target_status", "issue": f"No-op transition to same status '{target_val}'"}],
            )

        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if target_val not in allowed:
            raise ValidationException(
                message=f"Invalid state transition from '{current_status}' to '{target_val}'.",
                details=[{"field": "target_status", "issue": f"Transition from {current_status} to {target_val} is not permitted"}],
            )

        # Record audit log
        audit = self.repo.create_audit_log(
            db=self.db,
            incident_id=incident.incident_id,
            operator_id=operator_id,
            field="status",
            previous_value=current_status,
            new_value=target_val,
            reason=notes,
        )

        # Update status
        incident.status = target_val

        # Recalculate priority when status affects priority
        if target_val == "RESOLVED":
            incident.priority_score = 0.00
            incident.priority_level = "LOW"
            self.repo.create_priority_calculation(
                db=self.db,
                incident_id=incident.incident_id,
                priority_score=0.00,
                priority_level="LOW",
                factors=[],
                explanation="Incident marked RESOLVED: priority forced to 0.00 (LOW) and cleared from active dispatch.",
            )
        elif target_val == "FALSE_REPORT":
            incident.priority_score = 0.00
            incident.priority_level = "LOW"
            self.repo.create_priority_calculation(
                db=self.db,
                incident_id=incident.incident_id,
                priority_score=0.00,
                priority_level="LOW",
                factors=[],
                explanation="Incident classified as FALSE_REPORT: priority forced to 0.00 (LOW) and removed from active triage.",
            )
        else:
            # Deterministic calculation with state modifiers:
            # VERIFIED (+10), ESCALATED (+15), ACTIVE/NEEDS_REVIEW (standard)
            calc_res = calculate_priority(
                incident=incident,
                urgency=incident.urgency,
                people_at_risk_count=incident.people_at_risk_count,
                independent_sources=incident.independent_source_count,
                corroboration_score=float(incident.corroboration_score),
                incident_type=incident.incident_type,
                status=target_val,
            )
            incident.priority_score = calc_res.score
            incident.priority_level = calc_res.level.value

            self.repo.create_priority_calculation(
                db=self.db,
                incident_id=incident.incident_id,
                priority_score=calc_res.score,
                priority_level=calc_res.level.value,
                factors=[f.model_dump(mode="json") for f in calc_res.factors],
                explanation=calc_res.explanation,
                calc_version=calc_res.calc_version,
            )

        self.db.commit()
        self.db.refresh(incident)
        self.db.refresh(audit)

        incident_dto = self.assemble_single_incident(incident)
        audit_dto = AuditLogResponse.model_validate(audit)
        return incident_dto, audit_dto

    def override_incident(
        self,
        incident_id: str,
        field: str,
        new_value: Any,
        reason: str,
        x_operator_id: Optional[str] = None,
        body_operator_id: Optional[str] = None,
    ) -> tuple[IncidentResponse, AuditLogResponse]:
        """
        Execute an operator field override under row lock, record audit trail, update
        human_override snapshot, recompute priority when applicable, and commit atomically.
        """
        operator_id = resolve_operator_id(x_operator_id, body_operator_id)

        target_field = field.strip().lower()

        if target_field == "priority_level":
            raise ValidationException(
                message="Direct override of priority_level is not allowed; override priority_score instead.",
                details=[{"field": "field", "issue": "priority_level is derived from priority_score"}],
            )

        if target_field not in ALLOWED_OVERRIDE_FIELDS:
            raise ValidationException(
                message=f"Field '{field}' cannot be overridden. Allowed fields: {', '.join(sorted(ALLOWED_OVERRIDE_FIELDS))}.",
                details=[{"field": "field", "issue": f"Unrecognized override field '{field}'"}],
            )

        # Atomic lock
        incident = self.repo.get_incident_for_update(self.db, incident_id)
        if not incident:
            raise ResourceNotFoundException(f"Incident '{incident_id}' not found")

        prev_value: Any = None
        serialized_new_value: Any = None
        rerun_priority: bool = False
        direct_priority: bool = False

        if target_field == "urgency":
            if not isinstance(new_value, str) or new_value.strip().upper() not in {u.value for u in UrgencyLevel}:
                raise ValidationException(
                    message=f"Invalid urgency value '{new_value}'. Allowed: {', '.join(u.value for u in UrgencyLevel)}.",
                    details=[{"field": "new_value", "issue": "Must be valid UrgencyLevel"}],
                )
            normalized_urgency = new_value.strip().upper()
            prev_value = incident.urgency
            serialized_new_value = normalized_urgency
            incident.urgency = normalized_urgency
            rerun_priority = True

        elif target_field == "incident_type":
            if new_value is not None:
                if not isinstance(new_value, str) or new_value.strip().upper() not in {it.value for it in IncidentType}:
                    raise ValidationException(
                        message=f"Invalid incident_type value '{new_value}'. Allowed: {', '.join(it.value for it in IncidentType)} or null.",
                        details=[{"field": "new_value", "issue": "Must be valid IncidentType"}],
                    )
                normalized_type = new_value.strip().upper()
            else:
                normalized_type = None
            prev_value = incident.incident_type
            serialized_new_value = normalized_type
            incident.incident_type = normalized_type
            rerun_priority = True

        elif target_field == "people_at_risk_count":
            if new_value is not None:
                if isinstance(new_value, bool) or not isinstance(new_value, int) or new_value < 0:
                    raise ValidationException(
                        message=f"Invalid people_at_risk_count '{new_value}'. Must be an integer >= 0 or null.",
                        details=[{"field": "new_value", "issue": "Must be non-negative integer"}],
                    )
                count_val: Optional[int] = int(new_value)
            else:
                count_val = None
            prev_value = incident.people_at_risk_count
            serialized_new_value = count_val
            incident.people_at_risk_count = count_val
            rerun_priority = True

        elif target_field == "location":
            if not isinstance(new_value, dict):
                raise ValidationException(
                    message="Location override payload must be a JSON object with text, latitude, longitude, and precision.",
                    details=[{"field": "new_value", "issue": "Location must be an object"}],
                )
            loc_text = new_value.get("text")
            if loc_text is not None and not isinstance(loc_text, str):
                raise ValidationException(
                    message="Location text must be a string or null.",
                    details=[{"field": "new_value.text", "issue": "Text must be string"}],
                )
            lat = new_value.get("latitude")
            if lat is not None:
                if isinstance(lat, bool) or not isinstance(lat, (int, float)) or lat < -90.0 or lat > 90.0:
                    raise ValidationException(
                        message=f"Latitude must be a float in range [-90.0, 90.0] (received {lat}).",
                        details=[{"field": "new_value.latitude", "issue": "Latitude out of bounds"}],
                    )
                lat = float(lat)
            lon = new_value.get("longitude")
            if lon is not None:
                if isinstance(lon, bool) or not isinstance(lon, (int, float)) or lon < -180.0 or lon > 180.0:
                    raise ValidationException(
                        message=f"Longitude must be a float in range [-180.0, 180.0] (received {lon}).",
                        details=[{"field": "new_value.longitude", "issue": "Longitude out of bounds"}],
                    )
                lon = float(lon)
            prec = new_value.get("precision", "unknown")
            if not isinstance(prec, str) or prec.lower() not in {p.value for p in LocationPrecision}:
                raise ValidationException(
                    message=f"Invalid precision '{prec}'. Allowed: exact, approximate, unknown.",
                    details=[{"field": "new_value.precision", "issue": "Precision must be valid"}],
                )
            prec = prec.lower()

            prev_value = {
                "text": incident.location_text,
                "latitude": incident.latitude,
                "longitude": incident.longitude,
                "precision": incident.location_precision,
            }
            serialized_new_value = {
                "text": loc_text,
                "latitude": lat,
                "longitude": lon,
                "precision": prec,
            }
            incident.location_text = loc_text
            incident.latitude = lat
            incident.longitude = lon
            incident.location_precision = prec

        elif target_field == "required_response":
            if not isinstance(new_value, list):
                raise ValidationException(
                    message="Required response must be an array of canonical response capability strings.",
                    details=[{"field": "new_value", "issue": "Must be an array"}],
                )
            valid_caps = {c.value for c in ResponseCapability}
            normalized_responses: list[str] = []
            for r in new_value:
                if not isinstance(r, str) or r.strip().upper() not in valid_caps:
                    raise ValidationException(
                        message=f"Invalid response capability '{r}'. Allowed: {', '.join(sorted(valid_caps))}.",
                        details=[{"field": "new_value", "issue": f"Unrecognized capability '{r}'"}],
                    )
                normalized_responses.append(r.strip().upper())

            # Deduplicate and sort in stable canonical order
            dedup_set = set(normalized_responses)
            ordered_responses = [c for c in CANONICAL_RESPONSE_ORDER if c in dedup_set]
            remaining = sorted([c for c in dedup_set if c not in CANONICAL_RESPONSE_ORDER])
            final_responses = ordered_responses + remaining

            prev_value = list(incident.required_response or [])
            serialized_new_value = final_responses
            incident.required_response = final_responses

        elif target_field == "priority_score":
            if isinstance(new_value, bool) or not isinstance(new_value, (int, float)):
                raise ValidationException(
                    message="priority_score must be a numeric value in range [0.0, 100.0].",
                    details=[{"field": "new_value", "issue": "priority_score must be numeric"}],
                )
            score_f = float(new_value)
            if score_f < 0.0 or score_f > 100.0:
                raise ValidationException(
                    message=f"priority_score must be between 0.0 and 100.0 (received {score_f}).",
                    details=[{"field": "new_value", "issue": "priority_score out of bounds [0.0, 100.0]"}],
                )
            new_score = round(score_f, 2)
            new_level = map_priority_level(new_score).value

            prev_value = float(incident.priority_score)
            serialized_new_value = new_score
            incident.priority_score = new_score
            incident.priority_level = new_level
            direct_priority = True

        # Record AuditLog
        audit = self.repo.create_audit_log(
            db=self.db,
            incident_id=incident.incident_id,
            operator_id=operator_id,
            field=target_field,
            previous_value=prev_value,
            new_value=serialized_new_value,
            reason=reason,
        )

        # Update human_override snapshot
        existing_ho = incident.human_override or {}
        incident.human_override = {
            "active": True,
            "updated_by": operator_id,
            "updated_at": format_utc_now(),
            "reason": reason,
            "priority_overridden": existing_ho.get("priority_overridden", False) or direct_priority,
        }

        # Handle priority calculations
        if direct_priority:
            self.repo.create_priority_calculation(
                db=self.db,
                incident_id=incident.incident_id,
                priority_score=incident.priority_score,
                priority_level=incident.priority_level,
                factors=[],
                explanation=f"Manual priority override by operator {operator_id} to score {incident.priority_score:.2f} ({incident.priority_level}): {reason}",
                calc_version="human-override",
            )
        elif rerun_priority:
            calc_res = calculate_priority(
                incident=incident,
                urgency=incident.urgency,
                people_at_risk_count=incident.people_at_risk_count,
                independent_sources=incident.independent_source_count,
                corroboration_score=float(incident.corroboration_score),
                incident_type=incident.incident_type,
                status=incident.status,
            )
            incident.priority_score = calc_res.score
            incident.priority_level = calc_res.level.value

            self.repo.create_priority_calculation(
                db=self.db,
                incident_id=incident.incident_id,
                priority_score=calc_res.score,
                priority_level=calc_res.level.value,
                factors=[f.model_dump(mode="json") for f in calc_res.factors],
                explanation=calc_res.explanation,
                calc_version=calc_res.calc_version,
            )

        self.db.commit()
        self.db.refresh(incident)
        self.db.refresh(audit)

        incident_dto = self.assemble_single_incident(incident)
        audit_dto = AuditLogResponse.model_validate(audit)
        return incident_dto, audit_dto

    def get_incident_timeline(
        self,
        incident_id: str,
        order: str = "asc",
    ) -> IncidentTimelineResponse:
        """
        Synthesize chronological event audit trail from existing relational tables:
        - REPORT_FUSED from incident_reports join raw_reports (no raw-text snippets)
        - PRIORITY_CALCULATED from priority_calculations
        - STATUS_CHANGED and HUMAN_OVERRIDE from audit_logs
        Sorts deterministically by timestamp, then event_id.
        """
        norm_order = order.strip().lower()
        if norm_order not in ("asc", "desc"):
            raise ValidationException(
                message=f"Invalid order parameter '{order}'. Allowed: 'asc', 'desc'.",
                details=[{"field": "order", "issue": "Order must be 'asc' or 'desc'"}],
            )

        incident = self.repo.get_incident(self.db, incident_id)
        if not incident:
            raise ResourceNotFoundException(f"Incident '{incident_id}' not found")

        links_with_reports, calcs, audits = self.repo.get_timeline_records(self.db, incident_id)

        events: list[TimelineEvent] = []

        # 1. Report fusion events
        for link, report in links_with_reports:
            events.append(
                TimelineEvent(
                    event_id=link.id,
                    event_type="REPORT_FUSED",
                    timestamp=link.fused_at,
                    summary=f"Report {report.report_id} fused into incident ({link.relationship_type})",
                    details={
                        "report_id": report.report_id,
                        "relationship_type": link.relationship_type,
                        "similarity_score": float(link.similarity_score) if link.similarity_score is not None else None,
                        "source": report.source,
                    },
                )
            )

        # 2. Priority calculation events
        for calc in calcs:
            events.append(
                TimelineEvent(
                    event_id=calc.calc_id,
                    event_type="PRIORITY_CALCULATED",
                    timestamp=calc.calculated_at,
                    summary=f"Priority calculated: {float(calc.priority_score):.2f} ({calc.priority_level})",
                    details={
                        "score": float(calc.priority_score),
                        "level": calc.priority_level,
                        "explanation": calc.explanation,
                        "calc_version": calc.calc_version,
                    },
                )
            )

        # 3. Audit trail events
        for audit in audits:
            if audit.field == "status":
                etype = "STATUS_CHANGED"
                summary = f"Status changed from {audit.previous_value} to {audit.new_value} by {audit.operator_id}"
            else:
                etype = "HUMAN_OVERRIDE"
                summary = f"Operator {audit.operator_id} overrode {audit.field}"

            events.append(
                TimelineEvent(
                    event_id=audit.override_id,
                    event_type=etype,
                    timestamp=audit.created_at,
                    summary=summary,
                    details={
                        "operator_id": audit.operator_id,
                        "field": audit.field,
                        "previous_value": audit.previous_value,
                        "new_value": audit.new_value,
                        "reason": audit.reason,
                    },
                )
            )

        # Deterministic sort by timestamp, then event_id
        reverse = (norm_order == "desc")
        events.sort(key=lambda e: (e.timestamp, e.event_id), reverse=reverse)

        return IncidentTimelineResponse(
            incident_id=incident_id,
            total_events=len(events),
            events=events,
        )
