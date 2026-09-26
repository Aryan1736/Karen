"""
Karen's Ear — Raw Emergency Report ORM Model
Table: raw_reports
Append-only immutable log of ingested dispatches.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, func, text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.link import IncidentReportLink
    from backend.app.models.ml import MLPrediction


class RawReport(Base):
    """
    Stores incoming emergency dispatches.
    Raw report text is immutable once ingested.
    """
    __tablename__ = "raw_reports"
    __table_args__ = (
        CheckConstraint(
            "source IN ('manual', 'simulator', 'dataset', 'other')",
            name="check_raw_reports_source",
        ),
        CheckConstraint(
            "length(text) >= 3 AND length(text) <= 4000",
            name="check_raw_reports_text_length",
        ),
    )

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa_text("false"),
    )
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location_hint: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    # Database column is named 'metadata', mapped to 'metadata_' to prevent SQLAlchemy collision
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships (append-only, no cascade deletes)
    ml_prediction: Mapped[Optional["MLPrediction"]] = relationship(
        back_populates="raw_report",
        uselist=False,
    )
    incident_link: Mapped[Optional["IncidentReportLink"]] = relationship(
        back_populates="raw_report",
        uselist=False,
    )
