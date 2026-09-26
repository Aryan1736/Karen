"""
Karen's Ear — ORM Models & Pydantic Schemas Test Suite
Validates metadata, constraints, Pydantic validation rules, and JSON serialization.
"""
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any
import pytest
from pydantic import ValidationError

# Ensure workspace root is in sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.db.base import Base
import backend.app.models as models
from backend.app.schemas import (
    AuditLogResponse,
    ConfidenceBlock,
    Corroboration,
    HumanOverrideBlock,
    IncidentLocation,
    IncidentOverrideRequest,
    IncidentResponse,
    IncidentReviewRequest,
    IncidentRisk,
    IncidentStatus,
    IncidentType,
    LocationHint,
    LocationPrecision,
    MLPredictionOutput,
    LocationPrediction,
    PriorityBlock,
    PriorityFactor,
    PriorityLevel,
    ProcessingStatus,
    RawReportCreate,
    RawReportResponse,
    ResponseCapability,
    ResponseNeed,
    RiskPrediction,
    SimulationRunResponse,
    SimulationStartRequest,
    SimulationStatus,
    SourceType,
    TypePrediction,
    UrgencyLevel,
    UrgencyPrediction,
)


def test_seven_tables_registered_in_metadata():
    """Verify all 7 operational tables are properly registered in SQLAlchemy Base.metadata."""
    expected_tables = {
        "raw_reports",
        "ml_predictions",
        "incidents",
        "incident_reports",
        "priority_calculations",
        "audit_logs",
        "simulation_runs",
    }
    registered = set(Base.metadata.tables.keys())
    assert registered == expected_tables, f"Registered tables mismatch: {registered}"


def test_column_types_and_nullability():
    """Verify primary keys, unique constraints, and nullability across tables."""
    raw_reports = Base.metadata.tables["raw_reports"]
    assert raw_reports.c.report_id.primary_key
    assert not raw_reports.c.text.nullable
    assert not raw_reports.c.source.nullable
    assert not raw_reports.c.is_synthetic.nullable
    assert not raw_reports.c.reported_at.nullable
    assert raw_reports.c.location_hint.nullable
    assert "metadata" in raw_reports.c
    assert raw_reports.c["metadata"].nullable

    ml_predictions = Base.metadata.tables["ml_predictions"]
    assert ml_predictions.c.prediction_id.primary_key
    assert ml_predictions.c.report_id.unique
    assert not ml_predictions.c.report_id.nullable
    assert ml_predictions.c.embedding.nullable
    assert not ml_predictions.c.warnings.nullable

    incidents = Base.metadata.tables["incidents"]
    assert incidents.c.incident_id.primary_key
    assert not incidents.c.status.nullable
    assert not incidents.c.priority_score.nullable
    assert not incidents.c.required_response.nullable
    assert "source_report_ids" not in incidents.c

    incident_reports = Base.metadata.tables["incident_reports"]
    assert incident_reports.c.id.primary_key
    assert incident_reports.c.report_id.unique
    assert not incident_reports.c.incident_id.nullable

    audit_logs = Base.metadata.tables["audit_logs"]
    assert audit_logs.c.override_id.primary_key
    assert not audit_logs.c.reason.nullable


def test_check_constraints_and_indexes_exist():
    """Verify essential CheckConstraints and partial indexes are defined in metadata."""
    incidents = Base.metadata.tables["incidents"]
    constraint_names = {c.name for c in incidents.constraints}
    assert "check_incidents_status" in constraint_names
    assert "check_incidents_type" in constraint_names
    assert "check_incidents_priority_score" in constraint_names

    index_names = {idx.name for idx in incidents.indexes}
    assert "idx_incidents_active_priority" in index_names
    assert "idx_incidents_recent_active" in index_names

    ml_preds = Base.metadata.tables["ml_predictions"]
    ml_constraints = {c.name for c in ml_preds.constraints}
    assert "check_ml_predictions_embedding_dim" in ml_constraints
    assert "check_ml_predictions_processing_status" in ml_constraints

    audit_logs = Base.metadata.tables["audit_logs"]
    audit_constraints = {c.name for c in audit_logs.constraints}
    assert "check_audit_logs_reason_length" in audit_constraints


def test_raw_report_text_length_and_source_validation():
    """Test RawReportCreate enforces [3, 4000] length and valid source enums."""
    now = datetime.now(timezone.utc)

    # Valid report
    r = RawReportCreate(
        text="Valid emergency report content",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
    )
    assert r.report_id.startswith("rep-")
    assert r.text == "Valid emergency report content"

    # Too short (< 3 chars)
    with pytest.raises(ValidationError):
        RawReportCreate(
            text="ab",
            source=SourceType.MANUAL,
            is_synthetic=False,
            reported_at=now,
        )

    # Too long (> 4000 chars)
    with pytest.raises(ValidationError):
        RawReportCreate(
            text="a" * 4001,
            source=SourceType.MANUAL,
            is_synthetic=False,
            reported_at=now,
        )

    # Invalid source enum
    with pytest.raises(ValidationError):
        RawReportCreate(
            text="Emergency dispatch",
            source="unknown_invalid_source",  # type: ignore
            is_synthetic=False,
            reported_at=now,
        )


def test_ml_payload_embedding_validation():
    """
    Test MLPredictionOutput embedding rules:
    - Omitted embedding is valid
    - Exactly 384 floats is valid
    - Explicit None/null embedding is invalid
    - Length != 384 is invalid
    """
    valid_base: dict[str, Any] = {
        "report_id": "rep-100",
        "model_version": "all-MiniLM-L6-v2+heuristic-v1",
        "incident_type": {"label": "FLOOD_FLASH_FLOOD", "confidence": 0.95},
        "urgency": {"label": "CRITICAL", "confidence": 0.90},
        "location": {
            "text": "Rasulgarh underpass",
            "latitude": 20.2961,
            "longitude": 85.8245,
            "precision": "approximate",
            "confidence": 0.85,
        },
        "people_at_risk": {"count": 4, "confidence": 0.80},
        "required_response": [{"type": "SEARCH_AND_RESCUE", "confidence": 0.92}],
        "entities": [{"text": "underpass", "type": "LOCATION", "confidence": 0.90}],
        "processing_status": "SUCCESS",
        "warnings": [],
    }

    # 1. Valid without embedding field
    out_no_emb = MLPredictionOutput.model_validate(valid_base)
    assert out_no_emb.embedding is None

    # 2. Valid with exactly 384 floats
    valid_base["embedding"] = [0.05] * 384
    out_with_emb = MLPredictionOutput.model_validate(valid_base)
    assert len(out_with_emb.embedding) == 384

    # 3. Invalid with explicit null/None
    valid_base["embedding"] = None
    with pytest.raises(ValidationError) as exc_info:
        MLPredictionOutput.model_validate(valid_base)
    assert "cannot be explicitly null" in str(exc_info.value)

    # 4. Invalid with 383 floats (too short)
    valid_base["embedding"] = [0.05] * 383
    with pytest.raises(ValidationError):
        MLPredictionOutput.model_validate(valid_base)

    # 5. Invalid with 385 floats (too long)
    valid_base["embedding"] = [0.05] * 385
    with pytest.raises(ValidationError):
        MLPredictionOutput.model_validate(valid_base)


def test_confidence_range_validation():
    """Verify model confidences are bounded strictly to [0.0, 1.0]."""
    # Over 1.0
    with pytest.raises(ValidationError):
        TypePrediction(label=IncidentType.FLOOD_FLASH_FLOOD, confidence=1.05)

    # Under 0.0
    with pytest.raises(ValidationError):
        TypePrediction(label=IncidentType.FLOOD_FLASH_FLOOD, confidence=-0.1)

    # Valid
    p = TypePrediction(label=IncidentType.FLOOD_FLASH_FLOOD, confidence=0.88)
    assert p.confidence == 0.88


def test_audit_override_reason_length():
    """Verify operator override request requires at least 5 characters for reason."""
    # < 5 chars -> rejected
    with pytest.raises(ValidationError):
        IncidentOverrideRequest(
            operator_id="op_1",
            field="urgency",
            new_value="CRITICAL",
            reason="oops",
        )

    # >= 5 chars -> valid
    req = IncidentOverrideRequest(
        operator_id="op_1",
        field="urgency",
        new_value="CRITICAL",
        reason="Visual confirmation from field unit",
    )
    assert req.reason == "Visual confirmation from field unit"


def test_incident_response_json_serialization():
    """Verify IncidentResponse serializes timestamps strictly to ISO-8601 UTC with 'Z'."""
    now = datetime.now(timezone.utc)
    inc = IncidentResponse(
        incident_id="inc-test-01",
        status=IncidentStatus.ACTIVE,
        incident_type=IncidentType.FLOOD_FLASH_FLOOD,
        urgency=UrgencyLevel.CRITICAL,
        location=IncidentLocation(
            text="Patia Square",
            latitude=20.3533,
            longitude=85.8189,
            precision=LocationPrecision.APPROXIMATE,
        ),
        people_at_risk=IncidentRisk(count=3),
        required_response=["SEARCH_AND_RESCUE", "MEDICAL_EMS"],
        source_report_ids=["rep-1", "rep-2"],
        corroboration=Corroboration(
            report_count=2,
            independent_source_count=2,
            score=0.65,
            explanation="Corroborated by 2 distinct reports.",
        ),
        ml_confidence=ConfidenceBlock(overall=0.90, components={"type": 0.95}),
        priority=PriorityBlock(
            score=82.5,
            level=PriorityLevel.CRITICAL,
            explanation="Elevated due to life safety.",
            factors=[
                PriorityFactor(
                    factor="Urgency",
                    value="CRITICAL",
                    weight=0.35,
                    contribution=35.0,
                )
            ],
        ),
        human_override=HumanOverrideBlock(active=False),
        is_synthetic=False,
        created_at=now,
        updated_at=now,
    )

    dumped = inc.model_dump(mode="json")
    assert dumped["created_at"].endswith("Z")
    assert dumped["updated_at"].endswith("Z")
    assert dumped["priority"]["score"] == 82.5
    assert dumped["location"]["latitude"] == 20.3533
    assert dumped["source_report_ids"] == ["rep-1", "rep-2"]
