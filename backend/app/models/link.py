"""
Karen's Ear — Incident-Report Relationship Join Table ORM Model
Table: incident_reports
Tracks linkages, deduplication, and corroboration between raw reports and incidents.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.incident import Incident
    from backend.app.models.report import RawReport


class IncidentReportLink(Base):
    """
    Join table linking dispatches to incidents.
    Each report belongs to at most one incident (report_id is unique).
    """
    __tablename__ = "incident_reports"
    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('INITIAL', 'CORROBORATING', 'DUPLICATE', 'RELATED', 'UNCERTAIN')",
            name="check_incident_reports_relationship_type",
        ),
        CheckConstraint(
            "similarity_score IS NULL OR (similarity_score >= 0.0 AND similarity_score <= 1.0)",
            name="check_incident_reports_similarity_score",
        ),
        Index("idx_incident_reports_incident", "incident_id"),
        Index("idx_incident_reports_report", "report_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.incident_id"),
        nullable=False,
    )
    report_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("raw_reports.report_id"),
        unique=True,
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    similarity_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    fused_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    incident: Mapped["Incident"] = relationship(back_populates="report_links")
    raw_report: Mapped["RawReport"] = relationship(back_populates="incident_link")
