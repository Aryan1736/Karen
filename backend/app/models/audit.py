"""
Karen's Ear — Human Override Audit Log ORM Model
Table: audit_logs
Immutable ledger of all operator overrides and administrative status changes.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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


class AuditLog(Base):
    """
    Append-only immutable audit record of human intervention.
    Enforces justification reason length of at least 5 characters.
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint("length(reason) >= 5", name="check_audit_logs_reason_length"),
        Index("idx_audit_logs_incident", "incident_id", text("created_at DESC")),
    )

    override_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.incident_id"),
        nullable=False,
    )
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_value: Mapped[Any] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Any] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    incident: Mapped["Incident"] = relationship(back_populates="audit_logs")
