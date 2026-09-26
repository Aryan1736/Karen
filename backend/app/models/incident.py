"""
Karen's Ear — Incident ORM Model
Table: incidents
Represents the living, consolidated emergency situation presented to dispatchers.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.audit import AuditLog
    from backend.app.models.link import IncidentReportLink
    from backend.app.models.priority import PriorityCalculation


class Incident(Base):
    """
    Actionable tactical emergency incident.
    Source report IDs are dynamically resolved via report_links.
    """
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('NEW', 'ANALYZING', 'ACTIVE', 'NEEDS_REVIEW', 'VERIFIED', 'ESCALATED', 'RESOLVED', 'FALSE_REPORT')",
            name="check_incidents_status",
        ),
        CheckConstraint(
            "incident_type IS NULL OR incident_type IN ("
            "'FLOOD_FLASH_FLOOD', 'FIRE_WILDFIRE_EXPLOSION', 'STRUCTURAL_COLLAPSE', "
            "'EARTHQUAKE_LANDSLIDE', 'SEVERE_WEATHER_STORM', 'MEDICAL_EMERGENCY', "
            "'CIVIL_UNREST_ACTIVE_THREAT', 'UTILITY_INFRASTRUCTURE_FAILURE', 'OTHER_GENERAL_INCIDENT')",
            name="check_incidents_type",
        ),
        CheckConstraint(
            "urgency IS NULL OR urgency IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')",
            name="check_incidents_urgency",
        ),
        CheckConstraint(
            "priority_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')",
            name="check_incidents_priority_level",
        ),
        CheckConstraint(
            "location_precision IN ('exact', 'approximate', 'unknown')",
            name="check_incidents_location_precision",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90.0 AND latitude <= 90.0)",
            name="check_incidents_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180.0 AND longitude <= 180.0)",
            name="check_incidents_longitude",
        ),
        CheckConstraint(
            "priority_score >= 0.0 AND priority_score <= 100.0",
            name="check_incidents_priority_score",
        ),
        CheckConstraint(
            "corroboration_score >= 0.0 AND corroboration_score <= 1.0",
            name="check_incidents_corroboration_score",
        ),
        CheckConstraint("report_count >= 1", name="check_incidents_report_count"),
        CheckConstraint(
            "independent_source_count >= 1",
            name="check_incidents_independent_source_count",
        ),
        CheckConstraint(
            "people_at_risk_count IS NULL OR people_at_risk_count >= 0",
            name="check_incidents_people_at_risk_count",
        ),
        # Indexes specified in architecture/database.md Section 5
        Index(
            "idx_incidents_active_priority",
            text("priority_score DESC"),
            "status",
            postgresql_where=text("status IN ('ACTIVE', 'NEEDS_REVIEW', 'VERIFIED', 'ESCALATED')"),
        ),
        Index(
            "idx_incidents_recent_active",
            text("updated_at DESC"),
            postgresql_where=text("status IN ('ACTIVE', 'NEEDS_REVIEW')"),
        ),
    )

    incident_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    incident_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    urgency: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    location_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(DOUBLE_PRECISION, nullable=True)
    location_precision: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
    )
    people_at_risk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    required_response: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    priority_score: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=0.00,
        server_default=text("0.00"),
    )
    priority_level: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="LOW",
        server_default=text("'LOW'"),
    )
    corroboration_score: Mapped[float] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        default=0.000,
        server_default=text("0.000"),
    )
    report_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    independent_source_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    human_override: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default={"active": False},
        server_default=text("'{\"active\": false}'"),
    )
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    report_links: Mapped[list["IncidentReportLink"]] = relationship(
        back_populates="incident",
    )
    priority_calculations: Mapped[list["PriorityCalculation"]] = relationship(
        back_populates="incident",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="incident",
    )
