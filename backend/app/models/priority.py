"""
Karen's Ear — Priority Calculation History ORM Model
Table: priority_calculations
Historical log of every priority score adjustment for full explainability and replay.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.incident import Incident


class PriorityCalculation(Base):
    """
    Append-only ledger of priority computations.
    Provides complete mathematical traceability for operational decisions.
    """
    __tablename__ = "priority_calculations"
    __table_args__ = (
        CheckConstraint(
            "priority_score >= 0.0 AND priority_score <= 100.0",
            name="check_priority_calculations_score",
        ),
        CheckConstraint(
            "priority_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')",
            name="check_priority_calculations_level",
        ),
        Index("idx_priority_calculations_incident", "incident_id", text("calculated_at DESC")),
    )

    calc_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.incident_id"),
        nullable=False,
    )
    priority_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    priority_level: Mapped[str] = mapped_column(String(16), nullable=False)
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    calc_version: Mapped[str] = mapped_column(String(32), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    incident: Mapped["Incident"] = relationship(back_populates="priority_calculations")
