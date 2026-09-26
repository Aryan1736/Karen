"""
Karen's Ear — ML Prediction ORM Model
Table: ml_predictions
Advisory machine learning output associated with an ingested report.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, REAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.report import RawReport


class MLPrediction(Base):
    """
    Stores advisory NLP and classification output for a single report.
    One-to-one relationship with RawReport.
    """
    __tablename__ = "ml_predictions"
    __table_args__ = (
        CheckConstraint(
            "embedding IS NULL OR cardinality(embedding) = 384",
            name="check_ml_predictions_embedding_dim",
        ),
        CheckConstraint(
            "processing_status IN ('SUCCESS', 'PARTIAL', 'FAILED', 'NEEDS_REVIEW')",
            name="check_ml_predictions_processing_status",
        ),
        CheckConstraint(
            "overall_confidence IS NULL OR (overall_confidence >= 0.0 AND overall_confidence <= 1.0)",
            name="check_ml_predictions_overall_confidence",
        ),
    )

    prediction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("raw_reports.report_id"),
        unique=True,
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    incident_type: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    urgency: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    location: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    people_at_risk: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    required_response: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    entities: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    embedding_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(ARRAY(REAL), nullable=True)
    overall_confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    warnings: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("'{}'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    raw_report: Mapped["RawReport"] = relationship(back_populates="ml_prediction")
