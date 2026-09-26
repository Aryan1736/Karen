"""
Karen's Ear — Ingestion Data Access Repository
Encapsulates atomic database interactions for RawReport, MLPrediction, Incident,
IncidentReportLink, and PriorityCalculation tables.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.engine.priority import PriorityCalculationResult
from backend.app.models.incident import Incident
from backend.app.models.link import IncidentReportLink
from backend.app.models.ml import MLPrediction
from backend.app.models.priority import PriorityCalculation
from backend.app.models.report import RawReport
from backend.app.schemas.common import RelationshipType
from backend.app.schemas.ml import MLPredictionOutput
from backend.app.schemas.report import RawReportCreate


class IngestionRepository:
    """Repository managing relational persistence for the emergency ingestion pipeline."""

    @staticmethod
    def get_raw_report(db: Session, report_id: str) -> Optional[RawReport]:
        """Fetch raw report by primary key report_id."""
        return db.get(RawReport, report_id)

    @staticmethod
    def create_raw_report(db: Session, report_create: RawReportCreate) -> RawReport:
        """Create and stage a new RawReport entity."""
        location_hint_dict: Optional[dict[str, Any]] = None
        if report_create.location_hint is not None:
            location_hint_dict = report_create.location_hint.model_dump(mode="json")

        report = RawReport(
            report_id=report_create.report_id,
            text=report_create.text,
            source=report_create.source.value if hasattr(report_create.source, "value") else str(report_create.source),
            is_synthetic=report_create.is_synthetic,
            reported_at=report_create.reported_at,
            location_hint=location_hint_dict,
            metadata_=report_create.metadata,
        )
        db.add(report)
        db.flush()
        return report

    @staticmethod
    def get_ml_prediction(db: Session, report_id: str) -> Optional[MLPrediction]:
        """Fetch MLPrediction for a given report_id."""
        stmt = select(MLPrediction).where(MLPrediction.report_id == report_id)
        return db.scalars(stmt).first()

    @staticmethod
    def create_ml_prediction(db: Session, prediction: MLPredictionOutput) -> MLPrediction:
        """Create and stage a new MLPrediction entity."""
        record = MLPrediction(
            prediction_id=f"pred-{uuid.uuid4()}",
            report_id=prediction.report_id,
            model_version=prediction.model_version,
            incident_type=prediction.incident_type.model_dump(mode="json"),
            urgency=prediction.urgency.model_dump(mode="json"),
            location=prediction.location.model_dump(mode="json"),
            people_at_risk=prediction.people_at_risk.model_dump(mode="json"),
            required_response=[r.model_dump(mode="json") for r in prediction.required_response],
            entities=[e.model_dump(mode="json") for e in prediction.entities],
            embedding_reference=prediction.embedding_reference,
            embedding=prediction.embedding,
            overall_confidence=prediction.overall_confidence,
            processing_status=prediction.processing_status.value if hasattr(prediction.processing_status, "value") else str(prediction.processing_status),
            warnings=list(prediction.warnings),
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def get_candidate_incidents(
        db: Session,
        is_synthetic: bool,
        max_age_hours: float = 6.0,
    ) -> list[Incident]:
        """
        Query candidate incidents for correlation:
        - Status in ('ACTIVE', 'NEEDS_REVIEW')
        - Strict synthetic safety partition (real only correlates with real, synthetic with synthetic)
        - Updated within exactly the last max_age_hours (default 6h)
        - Ordered by updated_at descending
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        stmt = (
            select(Incident)
            .where(
                Incident.status.in_(["ACTIVE", "NEEDS_REVIEW"]),
                Incident.is_synthetic == is_synthetic,
                Incident.updated_at >= cutoff,
            )
            .order_by(Incident.updated_at.desc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_incident(db: Session, incident_id: str) -> Optional[Incident]:
        """Fetch incident by primary key incident_id."""
        return db.get(Incident, incident_id)

    @staticmethod
    def get_incident_link_by_report_id(db: Session, report_id: str) -> Optional[IncidentReportLink]:
        """Fetch join link between report and incident."""
        stmt = select(IncidentReportLink).where(IncidentReportLink.report_id == report_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_incident_source_reports(db: Session, incident_id: str) -> list[RawReport]:
        """Fetch all RawReport entities linked to a specific incident."""
        stmt = (
            select(RawReport)
            .join(IncidentReportLink, IncidentReportLink.report_id == RawReport.report_id)
            .where(IncidentReportLink.incident_id == incident_id)
            .order_by(IncidentReportLink.fused_at.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_incident(db: Session, data: dict[str, Any]) -> Incident:
        """Create and stage a new Incident entity."""
        incident = Incident(
            incident_id=data["incident_id"],
            status=data["status"],
            incident_type=data.get("incident_type"),
            urgency=data.get("urgency"),
            location_text=data.get("location_text"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            location_precision=data.get("location_precision", "unknown"),
            people_at_risk_count=data.get("people_at_risk_count"),
            required_response=data.get("required_response", []),
            priority_score=data.get("priority_score", 0.00),
            priority_level=data.get("priority_level", "LOW"),
            corroboration_score=data.get("corroboration_score", 0.000),
            report_count=data.get("report_count", 1),
            independent_source_count=data.get("independent_source_count", 1),
            human_override=data.get("human_override", {"active": False}),
            is_synthetic=data.get("is_synthetic", False),
        )
        db.add(incident)
        db.flush()
        return incident

    @staticmethod
    def create_incident_report_link(
        db: Session,
        incident_id: str,
        report_id: str,
        relationship_type: RelationshipType | str,
        similarity_score: Optional[float] = None,
    ) -> IncidentReportLink:
        """Create and stage a join link between an incident and a report."""
        rel_str = relationship_type.value if hasattr(relationship_type, "value") else str(relationship_type)
        link = IncidentReportLink(
            id=f"link-{uuid.uuid4()}",
            incident_id=incident_id,
            report_id=report_id,
            relationship_type=rel_str,
            similarity_score=similarity_score,
        )
        db.add(link)
        db.flush()
        return link

    @staticmethod
    def create_priority_calculation(
        db: Session,
        incident_id: str,
        priority_result: PriorityCalculationResult,
    ) -> PriorityCalculation:
        """Create and stage an append-only PriorityCalculation historical ledger record."""
        calc = PriorityCalculation(
            calc_id=f"calc-{uuid.uuid4()}",
            incident_id=incident_id,
            priority_score=priority_result.score,
            priority_level=priority_result.level.value if hasattr(priority_result.level, "value") else str(priority_result.level),
            factors=[f.model_dump(mode="json") for f in priority_result.factors],
            explanation=priority_result.explanation,
            calc_version="v1.0-deterministic",
        )
        db.add(calc)
        db.flush()
        return calc
