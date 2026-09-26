"""
Karen's Ear — Emergency Report Ingestion Service
Orchestrates durable raw ingestion, advisory ML analysis, candidate correlation,
incident creation/fusion, and deterministic priority calculation.
Strictly adheres to gemini.md, architecture/failure-handling.md, and locked fusion decisions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import math
from typing import Any, Optional
import uuid

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app.core.exceptions import AppException, DatabaseUnavailableException
from backend.app.engine.correlation import (
    DEFAULT_CORROBORATION_THRESHOLD,
    DEFAULT_DUPLICATE_THRESHOLD,
    DEFAULT_SPATIAL_CLUSTER_RADIUS_KM,
    DEFAULT_TEMPORAL_CUTOFF_HOURS,
    DEFAULT_TEMPORAL_DECAY_HOURS,
    calculate_corroboration_score,
    correlate_report_to_incident,
    find_best_incident_match,
)
from backend.app.engine.priority import PriorityCalculationResult, calculate_priority
from backend.app.models.incident import Incident
from backend.app.models.ml import MLPrediction
from backend.app.models.report import RawReport
from backend.app.repositories.ingestion_repo import IngestionRepository
from backend.app.schemas.common import PriorityLevel, ProcessingStatus, RelationshipType
from backend.app.schemas.link import ReportIngestResult
from backend.app.schemas.report import RawReportCreate
from backend.app.services.ml_adapter import MLAdapter, get_ml_adapter

logger = logging.getLogger("karen.backend.ingestion")

# Urgency ranking hierarchy: CRITICAL > HIGH > MEDIUM > LOW
URGENCY_RANKS: dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}

# Location precision hierarchy: unknown < approximate < exact
PRECISION_RANKS: dict[str, int] = {
    "unknown": 1,
    "approximate": 2,
    "exact": 3,
}

CANONICAL_RESPONSE_ORDER: list[str] = [
    "SEARCH_AND_RESCUE",
    "MEDICAL_EMS",
    "FIRE_HAZMAT",
    "POLICE_SECURITY",
    "PUBLIC_WORKS_UTILITY",
]


INGESTION_LOW_CONFIDENCE_THRESHOLD: float = 0.60


def is_low_confidence_prediction(pred_record: MLPrediction) -> bool:
    """
    Evaluates whether an ML prediction has low extraction confidence (< 0.60),
    warranting operator inspection in the NEEDS_REVIEW queue per architecture/failure-handling.md.
    """
    if pred_record.overall_confidence is not None:
        return float(pred_record.overall_confidence) < INGESTION_LOW_CONFIDENCE_THRESHOLD
    components: list[float] = []
    if pred_record.incident_type and pred_record.incident_type.get("confidence") is not None:
        components.append(float(pred_record.incident_type["confidence"]))
    if pred_record.urgency and pred_record.urgency.get("confidence") is not None:
        components.append(float(pred_record.urgency["confidence"]))
    if pred_record.location and pred_record.location.get("confidence") is not None:
        components.append(float(pred_record.location["confidence"]))
    if components:
        return (sum(components) / len(components)) < INGESTION_LOW_CONFIDENCE_THRESHOLD
    return False


# ==============================================================================
# Locked Fusion Helper Functions
# ==============================================================================

def fuse_incident_type(
    existing_type: Optional[str],
    new_type: Optional[str],
    has_human_override: bool,
) -> tuple[Optional[str], bool]:
    """
    Locked Fusion Decision 1:
    - If active human override: keep existing.
    - If existing is null and new is non-null: adopt new.
    - If existing is non-null and new is same: keep existing.
    - If both non-null and conflict: preserve existing, route incident to NEEDS_REVIEW.
    Returns (fused_type, route_to_needs_review).
    """
    if has_human_override:
        return existing_type, False
    if existing_type is None and new_type is not None:
        return new_type, False
    if existing_type is not None and (new_type is None or existing_type == new_type):
        return existing_type, False
    if existing_type is not None and new_type is not None and existing_type != new_type:
        return existing_type, True
    return existing_type, False


def fuse_urgency(
    existing_urgency: Optional[str],
    new_urgency: Optional[str],
    has_human_override: bool,
) -> Optional[str]:
    """
    Locked Fusion Decision 2:
    - Use highest known urgency: CRITICAL > HIGH > MEDIUM > LOW.
    - Null does not replace a known value.
    - Active human override always wins.
    """
    if has_human_override:
        return existing_urgency
    if existing_urgency is None:
        return new_urgency
    if new_urgency is None:
        return existing_urgency

    rank_existing = URGENCY_RANKS.get(existing_urgency.upper(), 0)
    rank_new = URGENCY_RANKS.get(new_urgency.upper(), 0)
    return new_urgency if rank_new > rank_existing else existing_urgency


def fuse_people_at_risk(
    existing_count: Optional[int],
    new_count: Optional[int],
) -> Optional[int]:
    """
    Locked Fusion Decision 3:
    - Never sum report counts.
    - If both counts are known: max(existing, new).
    - If only one is known: keep the known value.
    - If both are null: remain null.
    """
    if existing_count is not None and new_count is not None:
        return max(existing_count, new_count)
    if existing_count is not None:
        return existing_count
    if new_count is not None:
        return new_count
    return None


def fuse_location(
    existing_lat: Optional[float],
    existing_lon: Optional[float],
    existing_prec: str,
    existing_text: Optional[str],
    new_lat: Optional[float],
    new_lon: Optional[float],
    new_prec: str,
    new_text: Optional[str],
    correlation_conflict: bool = False,
) -> tuple[Optional[float], Optional[float], str, Optional[str], bool]:
    """
    Locked Fusion Decision 4:
    - Precision ordering: unknown < approximate < exact.
    - If incident has no coordinates and new report has valid coordinates: adopt them.
    - If new location precision is strictly better: allow refinement.
    - If precision is equal or worse: preserve existing coordinates/location.
    - Conflicting locations detected by correlation must route to NEEDS_REVIEW.
    - Never invent coordinates.
    Returns (lat, lon, precision, text, route_to_needs_review).
    """
    if correlation_conflict:
        return existing_lat, existing_lon, existing_prec, existing_text, True

    has_existing_coords = existing_lat is not None and existing_lon is not None
    has_new_coords = new_lat is not None and new_lon is not None

    if not has_existing_coords and has_new_coords:
        return new_lat, new_lon, new_prec, new_text or existing_text, False

    rank_existing = PRECISION_RANKS.get(existing_prec.lower(), 1)
    rank_new = PRECISION_RANKS.get(new_prec.lower(), 1)

    if has_new_coords and rank_new > rank_existing:
        return new_lat, new_lon, new_prec, new_text or existing_text, False

    return existing_lat, existing_lon, existing_prec, existing_text, False


def fuse_required_response(
    existing_responses: list[str],
    new_responses: list[str],
) -> list[str]:
    """
    Locked Fusion Decision 5:
    - Deterministic set union of existing + new response types.
    - No duplicates.
    - Stable canonical order.
    """
    union_set = set(existing_responses).union(set(new_responses))
    ordered = [r for r in CANONICAL_RESPONSE_ORDER if r in union_set]
    remaining = sorted([r for r in union_set if r not in CANONICAL_RESPONSE_ORDER])
    return ordered + remaining


# ==============================================================================
# Ingestion Service
# ==============================================================================

class IngestionService:
    """Service handling multi-phase report ingestion and incident correlation."""

    def __init__(
        self,
        db: Session,
        ml_adapter: Optional[MLAdapter] = None,
        repository: Optional[IngestionRepository] = None,
    ) -> None:
        self.db = db
        self.ml_adapter = ml_adapter or get_ml_adapter()
        self.repo = repository or IngestionRepository()

    def _verify_immutable_payload_match(
        self,
        existing: RawReport,
        incoming: RawReportCreate,
    ) -> None:
        """
        Validates idempotency when report_id already exists:
        - If immutable fields match: valid idempotent request.
        - If immutable fields differ: raises REPORT_ID_CONFLICT (HTTP 400).
        """
        source_val = incoming.source.value if hasattr(incoming.source, "value") else str(incoming.source)
        if existing.text != incoming.text or existing.source != source_val or existing.is_synthetic != incoming.is_synthetic:
            raise AppException(
                code="REPORT_ID_CONFLICT",
                message="Report ID already exists with different payload.",
                status_code=400,
            )

        # Compare timestamps (normalize to UTC)
        t_exist = existing.reported_at
        t_incom = incoming.reported_at
        if t_exist.tzinfo is None:
            t_exist = t_exist.replace(tzinfo=timezone.utc)
        if t_incom.tzinfo is None:
            t_incom = t_incom.replace(tzinfo=timezone.utc)

        if abs((t_exist - t_incom).total_seconds()) > 1.0:
            raise AppException(
                code="REPORT_ID_CONFLICT",
                message="Report ID already exists with different payload.",
                status_code=400,
            )

    def ingest_report(self, report_create: RawReportCreate) -> ReportIngestResult:
        """
        End-to-end ingestion pipeline:
        Phase A: Durable RawReport persistence and commit.
        Phase B: Intelligence, correlation, fusion, and deterministic priority calculation.
        """
        # ---------------------------------------------------------------------
        # Step 0 & Phase A: Idempotency & Durable Raw Ingestion
        # ---------------------------------------------------------------------
        existing_report = self.repo.get_raw_report(self.db, report_create.report_id)

        if existing_report is not None:
            # Validate immutable fields match
            self._verify_immutable_payload_match(existing_report, report_create)

            # Check if this report already has an IncidentReportLink
            existing_link = self.repo.get_incident_link_by_report_id(self.db, existing_report.report_id)
            if existing_link is not None:
                # Fully processed before: return existing result
                pred = self.repo.get_ml_prediction(self.db, existing_report.report_id)
                status_val = ProcessingStatus.SUCCESS
                if pred is not None:
                    status_val = ProcessingStatus(pred.processing_status) if pred.processing_status in ProcessingStatus.__members__.values() else ProcessingStatus.SUCCESS

                rel_val = RelationshipType(existing_link.relationship_type) if existing_link.relationship_type in RelationshipType.__members__.values() else RelationshipType.INITIAL

                return ReportIngestResult(
                    report_id=existing_report.report_id,
                    incident_id=existing_link.incident_id,
                    is_new_incident=False,
                    relationship=rel_val,
                    processing_status=status_val,
                )

            # Raw report exists but was interrupted before linking; resume processing
            raw_report = existing_report
        else:
            # Phase A: Persist and commit RawReport immediately
            raw_report = self.repo.create_raw_report(self.db, report_create)
            try:
                self.db.commit()
                self.db.refresh(raw_report)
            except Exception as exc:
                self.db.rollback()
                if isinstance(exc, OperationalError):
                    raise DatabaseUnavailableException("Failed to persist raw emergency report") from exc
                raise

        # ---------------------------------------------------------------------
        # Phase B: Intelligence, Correlation, Fusion, Priority Transaction
        # ---------------------------------------------------------------------
        try:
            return self._execute_phase_b(raw_report)
        except AppException:
            # Re-raise known business/API exceptions directly
            raise
        except Exception as phase_b_exc:
            logger.exception(
                "Phase B processing failed for report %s: %s",
                raw_report.report_id,
                type(phase_b_exc).__name__,
            )
            self.db.rollback()

            # Execute single bounded recovery attempt
            return self._execute_bounded_recovery(raw_report)

    def _execute_phase_b(self, raw_report: RawReport) -> ReportIngestResult:
        """Executes Phase B intelligence, correlation, fusion, and priority calculations."""
        # 1. ML Analysis (reuse existing prediction if resuming)
        existing_pred = self.repo.get_ml_prediction(self.db, raw_report.report_id)
        if existing_pred is not None:
            pred_record = existing_pred
        else:
            pred_output = self.ml_adapter.analyze_report(
                text=raw_report.text,
                report_id=raw_report.report_id,
                location_hint=raw_report.location_hint,
            )
            pred_record = self.repo.create_ml_prediction(self.db, pred_output)

        # 2. Candidate Lookup (Locked Decision 6 & 7: 6h lookback + strict synthetic safety boundary)
        candidates = self.repo.get_candidate_incidents(
            self.db,
            is_synthetic=raw_report.is_synthetic,
            max_age_hours=6.0,
        )

        # 3. Correlation Engine Triangulation
        # Adapt raw_report attributes for correlation engine
        report_meta = raw_report.metadata_ if isinstance(raw_report.metadata_, dict) else {}
        report_source_id = report_meta.get("caller_id") or report_meta.get("source_id") or raw_report.source

        best_incident: Optional[Incident] = None
        best_result = None
        highest_score = -1.0

        for candidate in candidates:
            # Query linked source reports to check source independence
            candidate_sources = self.repo.get_incident_source_reports(self.db, candidate.incident_id)
            candidate_texts = [r.text for r in candidate_sources]
            candidate_source_ids = [
                (r.metadata_.get("caller_id") or r.metadata_.get("source_id") or r.source)
                if isinstance(r.metadata_, dict) else r.source
                for r in candidate_sources
            ]

            res = correlate_report_to_incident(
                report=raw_report,
                incident=candidate,
                report_text=raw_report.text,
                report_embedding=pred_record.embedding,
                report_timestamp=raw_report.reported_at,
                report_latitude=pred_record.location.get("latitude") if pred_record.location else None,
                report_longitude=pred_record.location.get("longitude") if pred_record.location else None,
                report_location_text=pred_record.location.get("text") if pred_record.location else None,
                report_source_id=report_source_id,
                incident_embedding=getattr(candidate, "embedding", None),
                incident_latitude=candidate.latitude,
                incident_longitude=candidate.longitude,
                incident_location_text=candidate.location_text,
                incident_timestamp=candidate.updated_at,
                current_report_count=candidate.report_count,
                current_independent_sources=candidate.independent_source_count,
                candidate_texts=candidate_texts,
                candidate_source_ids=candidate_source_ids,
                duplicate_threshold=DEFAULT_DUPLICATE_THRESHOLD,
                corroboration_threshold=DEFAULT_CORROBORATION_THRESHOLD,
                tau_decay_hours=DEFAULT_TEMPORAL_DECAY_HOURS,
                cutoff_hours=DEFAULT_TEMPORAL_CUTOFF_HOURS,
                spatial_cluster_radius_km=DEFAULT_SPATIAL_CLUSTER_RADIUS_KM,
            )

            if res.is_match and res.composite_score > highest_score:
                highest_score = res.composite_score
                best_incident = candidate
                best_result = res

        # 4. Create or Fuse Incident
        is_new_incident: bool
        relationship: RelationshipType
        incident: Incident
        type_conflict = False
        location_conflict = False

        if best_incident is not None and best_result is not None:
            # Fuse into existing candidate
            is_new_incident = False
            relationship = best_result.relationship
            incident = best_incident

            # Check human protection
            has_human_override = bool(incident.human_override and incident.human_override.get("active"))
            is_protected_status = incident.status in ("VERIFIED", "ESCALATED") or has_human_override

            # Update counts based on relationship
            if relationship == RelationshipType.CORROBORATING:
                incident.report_count += 1
                incident.independent_source_count += 1
            else:  # DUPLICATE, RELATED, UNCERTAIN
                incident.report_count += 1

            # Recalculate corroboration score
            incident.corroboration_score = round(1.0 - math.exp(-0.45 * incident.independent_source_count), 2)

            # Locked Decision 1: Incident Type
            new_type = pred_record.incident_type.get("label") if pred_record.incident_type else None
            fused_type, type_conflict = fuse_incident_type(incident.incident_type, new_type, has_human_override)
            incident.incident_type = fused_type

            # Locked Decision 2: Urgency
            new_urgency = pred_record.urgency.get("label") if pred_record.urgency else None
            incident.urgency = fuse_urgency(incident.urgency, new_urgency, has_human_override)

            # Locked Decision 3: People at Risk
            new_risk = pred_record.people_at_risk.get("count") if pred_record.people_at_risk else None
            incident.people_at_risk_count = fuse_people_at_risk(incident.people_at_risk_count, new_risk)

            # Locked Decision 4: Location
            pred_loc = pred_record.location or {}
            location_conflict = any("Conflicting locations" in w for w in best_result.warnings)
            f_lat, f_lon, f_prec, f_text, loc_conflict = fuse_location(
                existing_lat=incident.latitude,
                existing_lon=incident.longitude,
                existing_prec=incident.location_precision,
                existing_text=incident.location_text,
                new_lat=pred_loc.get("latitude"),
                new_lon=pred_loc.get("longitude"),
                new_prec=pred_loc.get("precision", "unknown"),
                new_text=pred_loc.get("text"),
                correlation_conflict=location_conflict,
            )
            incident.latitude = f_lat
            incident.longitude = f_lon
            incident.location_precision = f_prec
            incident.location_text = f_text

            # Locked Decision 5: Required Response
            new_responses = [
                r["type"] for r in (pred_record.required_response or [])
                if isinstance(r, dict) and "type" in r
            ]
            incident.required_response = fuse_required_response(incident.required_response or [], new_responses)

            # Status determination
            if not is_protected_status:
                if (
                    relationship == RelationshipType.UNCERTAIN
                    or pred_record.processing_status in ("FAILED", "PARTIAL", "NEEDS_REVIEW")
                    or is_low_confidence_prediction(pred_record)
                    or type_conflict
                    or loc_conflict
                ):
                    incident.status = "NEEDS_REVIEW"

            # Create link
            self.repo.create_incident_report_link(
                self.db,
                incident_id=incident.incident_id,
                report_id=raw_report.report_id,
                relationship_type=relationship,
                similarity_score=best_result.composite_score,
            )

        else:
            # Spawn NEW incident
            is_new_incident = True
            relationship = RelationshipType.INITIAL

            # Initial status: FAILED, PARTIAL ML, or low confidence (< 0.60) -> NEEDS_REVIEW, otherwise ACTIVE
            initial_status = (
                "NEEDS_REVIEW"
                if (
                    pred_record.processing_status in ("FAILED", "PARTIAL", "NEEDS_REVIEW")
                    or is_low_confidence_prediction(pred_record)
                )
                else "ACTIVE"
            )

            pred_loc = pred_record.location or {}
            new_responses = [
                r["type"] for r in (pred_record.required_response or [])
                if isinstance(r, dict) and "type" in r
            ]
            ordered_responses = fuse_required_response([], new_responses)

            inc_id = f"inc-{uuid.uuid4()}"
            incident = self.repo.create_incident(
                self.db,
                {
                    "incident_id": inc_id,
                    "status": initial_status,
                    "incident_type": pred_record.incident_type.get("label") if pred_record.incident_type else None,
                    "urgency": pred_record.urgency.get("label") if pred_record.urgency else None,
                    "location_text": pred_loc.get("text"),
                    "latitude": pred_loc.get("latitude"),
                    "longitude": pred_loc.get("longitude"),
                    "location_precision": pred_loc.get("precision", "unknown"),
                    "people_at_risk_count": pred_record.people_at_risk.get("count") if pred_record.people_at_risk else None,
                    "required_response": ordered_responses,
                    "priority_score": 0.00,
                    "priority_level": "LOW",
                    "corroboration_score": 0.36,  # round(1 - exp(-0.45 * 1), 2)
                    "report_count": 1,
                    "independent_source_count": 1,
                    "human_override": {"active": False},
                    "is_synthetic": raw_report.is_synthetic,
                },
            )

            # Link report to new incident
            self.repo.create_incident_report_link(
                self.db,
                incident_id=incident.incident_id,
                report_id=raw_report.report_id,
                relationship_type=RelationshipType.INITIAL,
                similarity_score=None,
            )

        # 5. Deterministic Priority Calculation
        if pred_record.processing_status == "FAILED":
            priority_res = PriorityCalculationResult(
                raw_score=50.0,
                score=50.0,
                level=PriorityLevel.MEDIUM,
                explanation="Automated ML scoring unavailable; routed to operator for manual triage.",
                factors=[],
            )
        else:
            ml_conf: Optional[dict[str, Any]] = None
            if pred_record.overall_confidence is not None:
                ml_conf = float(pred_record.overall_confidence)  # type: ignore
            else:
                components: dict[str, Optional[float]] = {}
                if pred_record.incident_type and pred_record.incident_type.get("confidence") is not None:
                    components["incident_type"] = pred_record.incident_type["confidence"]
                if pred_record.urgency and pred_record.urgency.get("confidence") is not None:
                    components["urgency"] = pred_record.urgency["confidence"]
                if pred_record.location and pred_record.location.get("confidence") is not None:
                    components["location"] = pred_record.location["confidence"]
                if components:
                    ml_conf = {"components": components}

            priority_res = calculate_priority(
                incident=incident,
                urgency=incident.urgency,
                people_at_risk_count=incident.people_at_risk_count,
                independent_sources=incident.independent_source_count,
                corroboration_score=float(incident.corroboration_score),
                incident_type=incident.incident_type,
                status=incident.status,
                ml_confidence=ml_conf,
            )

        incident.priority_score = priority_res.score
        incident.priority_level = priority_res.level.value if hasattr(priority_res.level, "value") else str(priority_res.level)

        # Record priority calculation in ledger
        self.repo.create_priority_calculation(
            self.db,
            incident_id=incident.incident_id,
            priority_result=priority_res,
        )

        # Commit Phase B
        self.db.commit()
        self.db.refresh(incident)

        status_enum = ProcessingStatus(pred_record.processing_status) if pred_record.processing_status in ProcessingStatus.__members__.values() else ProcessingStatus.SUCCESS

        return ReportIngestResult(
            report_id=raw_report.report_id,
            incident_id=incident.incident_id,
            is_new_incident=is_new_incident,
            relationship=relationship,
            processing_status=status_enum,
        )

    def _execute_bounded_recovery(self, raw_report: RawReport) -> ReportIngestResult:
        """Single bounded recovery attempt to create minimal FAILED prediction and NEEDS_REVIEW incident."""
        try:
            logger.info("Executing single bounded recovery for raw report %s", raw_report.report_id)
            fallback_pred = self.ml_adapter.make_fallback_prediction(
                report_id=raw_report.report_id,
                location_hint=raw_report.location_hint,
                warning_code="ML_ANALYSIS_FAILED",
            )
            pred_record = self.repo.create_ml_prediction(self.db, fallback_pred)

            inc_id = f"inc-{uuid.uuid4()}"
            pred_loc = pred_record.location or {}
            incident = self.repo.create_incident(
                self.db,
                {
                    "incident_id": inc_id,
                    "status": "NEEDS_REVIEW",
                    "incident_type": None,
                    "urgency": None,
                    "location_text": pred_loc.get("text"),
                    "latitude": pred_loc.get("latitude"),
                    "longitude": pred_loc.get("longitude"),
                    "location_precision": pred_loc.get("precision", "unknown"),
                    "people_at_risk_count": None,
                    "required_response": [],
                    "priority_score": 50.00,
                    "priority_level": "MEDIUM",
                    "corroboration_score": 0.36,
                    "report_count": 1,
                    "independent_source_count": 1,
                    "human_override": {"active": False},
                    "is_synthetic": raw_report.is_synthetic,
                },
            )

            self.repo.create_incident_report_link(
                self.db,
                incident_id=incident.incident_id,
                report_id=raw_report.report_id,
                relationship_type=RelationshipType.INITIAL,
                similarity_score=None,
            )

            fallback_priority = PriorityCalculationResult(
                raw_score=50.0,
                score=50.0,
                level=PriorityLevel.MEDIUM,
                explanation="Automated ML scoring unavailable; routed to operator for manual triage.",
                factors=[],
            )
            incident.priority_score = 50.00
            incident.priority_level = "MEDIUM"

            self.repo.create_priority_calculation(
                self.db,
                incident_id=incident.incident_id,
                priority_result=fallback_priority,
            )

            self.db.commit()
            return ReportIngestResult(
                report_id=raw_report.report_id,
                incident_id=incident.incident_id,
                is_new_incident=True,
                relationship=RelationshipType.INITIAL,
                processing_status=ProcessingStatus.FAILED,
            )

        except Exception as recovery_exc:
            logger.exception("Bounded recovery failed for report %s: %s", raw_report.report_id, type(recovery_exc).__name__)
            self.db.rollback()
            if isinstance(recovery_exc, OperationalError):
                raise DatabaseUnavailableException("Database service failed during recovery") from recovery_exc
            raise AppException(
                code="INTERNAL_SERVER_ERROR",
                message="Report ingested safely, but downstream analysis and recovery could not complete.",
                status_code=500,
            ) from recovery_exc


def get_ingestion_service(
    db: Session,
    ml_adapter: Optional[MLAdapter] = None,
) -> IngestionService:
    """Dependency helper constructing an IngestionService instance."""
    return IngestionService(db=db, ml_adapter=ml_adapter or get_ml_adapter())
