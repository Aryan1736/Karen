"""
Karen's Ear — Incident Data Access Repository
Encapsulates database access for incidents, relational linkages, priority calculations,
audit logs, and timeline events.
"""
from __future__ import annotations

from typing import Any, Optional
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog
from backend.app.models.incident import Incident
from backend.app.models.link import IncidentReportLink
from backend.app.models.ml import MLPrediction
from backend.app.models.priority import PriorityCalculation
from backend.app.models.report import RawReport


class IncidentRepository:
    """Repository managing relational persistence for incident operations."""

    @staticmethod
    def get_incident(db: Session, incident_id: str) -> Optional[Incident]:
        """Fetch an incident by primary key incident_id."""
        return db.get(Incident, incident_id)

    @staticmethod
    def get_incident_for_update(db: Session, incident_id: str) -> Optional[Incident]:
        """Fetch an incident with a row-level lock (SELECT ... FOR UPDATE)."""
        stmt = (
            select(Incident)
            .where(Incident.incident_id == incident_id)
            .with_for_update()
        )
        return db.scalars(stmt).first()

    @staticmethod
    def get_incidents(
        db: Session,
        statuses: Optional[list[str]] = None,
        levels: Optional[list[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Incident], int, int]:
        """
        Query incidents matching optional status and level filters.
        Ordering: priority_score DESC, updated_at DESC.
        Returns: (incidents_slice, total_count, critical_count).
        Both counts use the exact same filter scope before pagination.
        """
        base_query = select(Incident)
        if statuses:
            base_query = base_query.where(Incident.status.in_(statuses))
        if levels:
            base_query = base_query.where(Incident.priority_level.in_(levels))

        # Total count before pagination
        total_count = db.scalar(select(func.count()).select_from(base_query.subquery())) or 0

        # Critical count matching the same filters before pagination
        critical_count = (
            db.scalar(
                select(func.count()).select_from(
                    base_query.where(Incident.priority_level == "CRITICAL").subquery()
                )
            )
            or 0
        )

        # Paginated ordered query
        paged_stmt = (
            base_query.order_by(Incident.priority_score.desc(), Incident.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        incidents = list(db.scalars(paged_stmt).all())

        return incidents, total_count, critical_count

    @staticmethod
    def get_source_report_ids_for_incidents(
        db: Session,
        incident_ids: list[str],
    ) -> dict[str, list[str]]:
        """
        Fetch source_report_ids for a batch of incidents in fusion order (fused_at ASC).
        Returns a dict mapping incident_id to list of report_id.
        """
        if not incident_ids:
            return {}

        stmt = (
            select(IncidentReportLink.incident_id, IncidentReportLink.report_id)
            .where(IncidentReportLink.incident_id.in_(incident_ids))
            .order_by(IncidentReportLink.fused_at.asc())
        )
        mapping: dict[str, list[str]] = {inc_id: [] for inc_id in incident_ids}
        for inc_id, rep_id in db.execute(stmt).all():
            mapping.setdefault(inc_id, []).append(rep_id)
        return mapping

    @staticmethod
    def get_latest_priority_calculations_for_incidents(
        db: Session,
        incident_ids: list[str],
    ) -> dict[str, PriorityCalculation]:
        """
        Fetch the most recent PriorityCalculation for each incident.
        Uses PostgreSQL DISTINCT ON (incident_id) ordered by calculated_at DESC.
        """
        if not incident_ids:
            return {}

        stmt = (
            select(PriorityCalculation)
            .where(PriorityCalculation.incident_id.in_(incident_ids))
            .distinct(PriorityCalculation.incident_id)
            .order_by(PriorityCalculation.incident_id, PriorityCalculation.calculated_at.desc())
        )
        return {calc.incident_id: calc for calc in db.scalars(stmt).all()}

    @staticmethod
    def get_latest_ml_predictions_for_incidents(
        db: Session,
        incident_ids: list[str],
    ) -> dict[str, MLPrediction]:
        """
        Fetch the latest linked MLPrediction according to incident-report fusion order (fused_at DESC).
        Uses PostgreSQL DISTINCT ON (ir.incident_id).
        """
        if not incident_ids:
            return {}

        stmt = (
            select(IncidentReportLink.incident_id, MLPrediction)
            .join(MLPrediction, IncidentReportLink.report_id == MLPrediction.report_id)
            .where(IncidentReportLink.incident_id.in_(incident_ids))
            .distinct(IncidentReportLink.incident_id)
            .order_by(IncidentReportLink.incident_id, IncidentReportLink.fused_at.desc())
        )
        mapping: dict[str, MLPrediction] = {}
        for inc_id, pred in db.execute(stmt).all():
            mapping[inc_id] = pred
        return mapping

    @staticmethod
    def get_incident_source_reports(db: Session, incident_id: str) -> list[RawReport]:
        """Fetch all RawReport entities linked to a specific incident in fusion order."""
        stmt = (
            select(RawReport)
            .join(IncidentReportLink, IncidentReportLink.report_id == RawReport.report_id)
            .where(IncidentReportLink.incident_id == incident_id)
            .order_by(IncidentReportLink.fused_at.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_incident_audit_trail(db: Session, incident_id: str) -> list[AuditLog]:
        """Fetch all AuditLog entries for an incident ordered by created_at DESC."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.incident_id == incident_id)
            .order_by(AuditLog.created_at.desc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def create_audit_log(
        db: Session,
        incident_id: str,
        operator_id: str,
        field: str,
        previous_value: Any,
        new_value: Any,
        reason: str,
    ) -> AuditLog:
        """Create and stage a new AuditLog record."""
        audit = AuditLog(
            override_id=f"ovr-{uuid.uuid4()}",
            incident_id=incident_id,
            operator_id=operator_id,
            field=field,
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
        )
        db.add(audit)
        db.flush()
        return audit

    @staticmethod
    def create_priority_calculation(
        db: Session,
        incident_id: str,
        priority_score: float,
        priority_level: str,
        factors: list[dict[str, Any]],
        explanation: str,
        calc_version: str = "v1.0-deterministic",
    ) -> PriorityCalculation:
        """Create and stage a new PriorityCalculation record."""
        calc = PriorityCalculation(
            calc_id=f"calc-{uuid.uuid4()}",
            incident_id=incident_id,
            priority_score=priority_score,
            priority_level=priority_level,
            factors=factors,
            explanation=explanation,
            calc_version=calc_version,
        )
        db.add(calc)
        db.flush()
        return calc

    @staticmethod
    def get_timeline_records(
        db: Session,
        incident_id: str,
    ) -> tuple[list[tuple[IncidentReportLink, RawReport]], list[PriorityCalculation], list[AuditLog]]:
        """
        Fetch all records needed to synthesize an incident timeline:
        - (IncidentReportLink, RawReport) tuples
        - PriorityCalculation records
        - AuditLog records
        """
        links_stmt = (
            select(IncidentReportLink, RawReport)
            .join(RawReport, IncidentReportLink.report_id == RawReport.report_id)
            .where(IncidentReportLink.incident_id == incident_id)
            .order_by(IncidentReportLink.fused_at.asc())
        )
        links_with_reports = list(db.execute(links_stmt).all())

        calcs_stmt = (
            select(PriorityCalculation)
            .where(PriorityCalculation.incident_id == incident_id)
            .order_by(PriorityCalculation.calculated_at.asc())
        )
        calcs = list(db.scalars(calcs_stmt).all())

        audits_stmt = (
            select(AuditLog)
            .where(AuditLog.incident_id == incident_id)
            .order_by(AuditLog.created_at.asc())
        )
        audits = list(db.scalars(audits_stmt).all())

        return links_with_reports, calcs, audits
