"""
Karen's Ear — Ingestion & Incident Correlation Integration Tests
Validates durable raw ingestion, correlation triangulation, locked fusion decisions,
priority calculations, idempotency, and failure degradation against local PostgreSQL.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Any, Generator, Optional
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.core.exceptions import AppException
from backend.app.db.session import SessionLocal
from backend.app.engine.priority import calculate_priority
from backend.app.models.incident import Incident
from backend.app.models.link import IncidentReportLink
from backend.app.models.ml import MLPrediction
from backend.app.models.priority import PriorityCalculation
from backend.app.models.report import RawReport
from backend.app.schemas.common import (
    IncidentType,
    LocationPrecision,
    ProcessingStatus,
    RelationshipType,
    ResponseCapability,
    SourceType,
    UrgencyLevel,
)
from backend.app.schemas.link import ReportIngestResult
from backend.app.schemas.ml import (
    LocationPrediction,
    MLPredictionOutput,
    ResponseNeed,
    RiskPrediction,
    TypePrediction,
    UrgencyPrediction,
)
from backend.app.schemas.report import LocationHint, RawReportCreate
from backend.app.services.ingestion import IngestionService
from backend.app.services.ml_adapter import MLAdapter


# Helper to build mock analyzer outputs
def build_mock_prediction(
    report_id: str,
    incident_type: Optional[str] = "FLOOD_FLASH_FLOOD",
    urgency: Optional[str] = "HIGH",
    risk_count: Optional[int] = 2,
    location_text: Optional[str] = "Rasulgarh underpass",
    latitude: Optional[float] = 20.2961,
    longitude: Optional[float] = 85.8245,
    precision: LocationPrecision = LocationPrecision.APPROXIMATE,
    required_response: Optional[list[str]] = None,
    processing_status: ProcessingStatus = ProcessingStatus.SUCCESS,
    overall_confidence: float = 0.85,
) -> MLPredictionOutput:
    req_list = []
    if required_response:
        for r in required_response:
            req_list.append(ResponseNeed(type=ResponseCapability(r), confidence=0.9))

    return MLPredictionOutput(
        report_id=report_id,
        model_version="mock-test-v1",
        incident_type=TypePrediction(
            label=IncidentType(incident_type) if incident_type else None,
            confidence=0.9 if incident_type else None,
        ),
        urgency=UrgencyPrediction(
            label=UrgencyLevel(urgency) if urgency else None,
            confidence=0.88 if urgency else None,
        ),
        location=LocationPrediction(
            text=location_text,
            latitude=latitude,
            longitude=longitude,
            precision=precision,
            confidence=0.85 if latitude else None,
        ),
        people_at_risk=RiskPrediction(count=risk_count, confidence=0.8 if risk_count else None),
        required_response=req_list,
        entities=[],
        embedding_reference=None,
        overall_confidence=overall_confidence,
        processing_status=processing_status,
        warnings=[],
    )


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Provides a dedicated SessionLocal and cleans up any records created during the test."""
    session = SessionLocal()
    created_prefix = "rep-test-"
    try:
        yield session
    finally:
        # Clean up records created by test runs to preserve local database state
        session.rollback()
        session.execute(text("DELETE FROM incident_reports WHERE report_id LIKE 'rep-test-%'"))
        session.execute(text("DELETE FROM ml_predictions WHERE report_id LIKE 'rep-test-%'"))
        session.execute(text("DELETE FROM raw_reports WHERE report_id LIKE 'rep-test-%'"))
        # Clean up orphaned test incidents
        session.execute(text("""
            DELETE FROM priority_calculations 
            WHERE incident_id IN (SELECT incident_id FROM incidents WHERE NOT EXISTS (SELECT 1 FROM incident_reports ir WHERE ir.incident_id = incidents.incident_id))
        """))
        session.execute(text("""
            DELETE FROM incidents 
            WHERE NOT EXISTS (SELECT 1 FROM incident_reports ir WHERE ir.incident_id = incidents.incident_id)
        """))
        session.commit()
        session.close()


def test_ingest_initial_report_creates_incident(db: Session):
    """Initial report ingestion creates RawReport, MLPrediction, Incident, Link, and PriorityCalculation."""
    rep_id = f"rep-test-{uuid.uuid4().hex[:8]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id, incident_type="FLOOD_FLASH_FLOOD", urgency="HIGH", risk_count=3)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    create_payload = RawReportCreate(
        report_id=rep_id,
        text="Flash flood warning near Rasulgarh underpass. 3 people trapped in car.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=datetime.now(timezone.utc),
        location_hint=LocationHint(raw_text="Rasulgarh underpass", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )

    result = service.ingest_report(create_payload)

    assert isinstance(result, ReportIngestResult)
    assert result.report_id == rep_id
    assert result.is_new_incident is True
    assert result.relationship == RelationshipType.INITIAL
    assert result.processing_status == ProcessingStatus.SUCCESS

    # Verify database state
    raw = db.get(RawReport, rep_id)
    assert raw is not None
    assert raw.text == create_payload.text

    pred = db.get(MLPrediction, rep_id) or db.query(MLPrediction).filter_by(report_id=rep_id).first()
    assert pred is not None
    assert pred.incident_type["label"] == "FLOOD_FLASH_FLOOD"

    incident = db.get(Incident, result.incident_id)
    assert incident is not None
    assert incident.status == "ACTIVE"
    assert incident.incident_type == "FLOOD_FLASH_FLOOD"
    assert incident.urgency == "HIGH"
    assert incident.people_at_risk_count == 3
    assert incident.report_count == 1
    assert incident.independent_source_count == 1
    assert float(incident.corroboration_score) == 0.36
    assert float(incident.priority_score) > 0.0

    # Verify link
    link = db.query(IncidentReportLink).filter_by(report_id=rep_id).first()
    assert link is not None
    assert link.incident_id == result.incident_id
    assert link.relationship_type == "INITIAL"

    # Verify priority calculation recorded in ledger
    calc = db.query(PriorityCalculation).filter_by(incident_id=result.incident_id).first()
    assert calc is not None
    assert calc.priority_score == incident.priority_score


def test_ingest_duplicate_report(db: Session):
    """Submitting near-identical report from same caller fuses as DUPLICATE with report_count +1 and independent_sources +0."""
    rep_id_1 = f"rep-test-dup-1-{uuid.uuid4().hex[:6]}"
    rep_id_2 = f"rep-test-dup-2-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id, incident_type="FLOOD_FLASH_FLOOD", urgency="HIGH", risk_count=2)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id_1,
        text="Flash flood water entering shops at Rasulgarh underpass.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        metadata={"caller_id": "+91-9876543210"},
        location_hint=LocationHint(raw_text="Rasulgarh underpass", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r1 = service.ingest_report(p1)

    # Identical caller reporting again shortly after
    p2 = RawReportCreate(
        report_id=rep_id_2,
        text="Flash flood water entering shops at Rasulgarh underpass. Still rising.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=5),
        metadata={"caller_id": "+91-9876543210"},
        location_hint=LocationHint(raw_text="Rasulgarh underpass", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r2 = service.ingest_report(p2)

    assert r2.is_new_incident is False
    assert r2.incident_id == r1.incident_id
    assert r2.relationship == RelationshipType.DUPLICATE

    inc = db.get(Incident, r1.incident_id)
    assert inc.report_count == 2
    assert inc.independent_source_count == 1
    assert float(inc.corroboration_score) == 0.36


def test_ingest_corroborating_independent_source(db: Session):
    """Submitting similar report from distinct independent caller fuses as CORROBORATING and increments independent_source_count."""
    rep_id_1 = f"rep-test-corrob-1-{uuid.uuid4().hex[:6]}"
    rep_id_2 = f"rep-test-corrob-2-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id, incident_type="FLOOD_FLASH_FLOOD", urgency="HIGH", risk_count=3)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id_1,
        text="Severe flooding at Rasulgarh flyover. Vehicles submerged.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        metadata={"caller_id": "+91-9876543210"},
        location_hint=LocationHint(raw_text="Rasulgarh flyover", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r1 = service.ingest_report(p1)

    # Distinct second caller with re-phrased eyewitness confirmation
    p2 = RawReportCreate(
        report_id=rep_id_2,
        text="Water level rising rapidly over cars near Rasulgarh underpass. Multiple people stranded.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=10),
        metadata={"caller_id": "+91-9123456780"},
        location_hint=LocationHint(raw_text="Rasulgarh underpass", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r2 = service.ingest_report(p2)

    assert r2.is_new_incident is False
    assert r2.incident_id == r1.incident_id
    assert r2.relationship == RelationshipType.CORROBORATING

    inc = db.get(Incident, r1.incident_id)
    assert inc.report_count == 2
    assert inc.independent_source_count == 2
    # 1 - exp(-0.45 * 2) = 0.593 -> round to 0.59
    assert float(inc.corroboration_score) == 0.59


def test_ingest_incident_type_conflict_preserves_and_routes_to_needs_review(db: Session):
    """When a new report has a conflicting incident_type, preserve existing type and set status = NEEDS_REVIEW."""
    rep_id_1 = f"rep-test-conf-1-{uuid.uuid4().hex[:6]}"
    rep_id_2 = f"rep-test-conf-2-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        if report_id == rep_id_1:
            return build_mock_prediction(report_id, incident_type="FLOOD_FLASH_FLOOD", urgency="HIGH")
        return build_mock_prediction(report_id, incident_type="FIRE_WILDFIRE_EXPLOSION", urgency="HIGH")

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id_1,
        text="Flash flood at Rasulgarh junction.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r1 = service.ingest_report(p1)

    p2 = RawReportCreate(
        report_id=rep_id_2,
        text="Major fire and explosion at Rasulgarh junction.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=5),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r2 = service.ingest_report(p2)

    assert r2.incident_id == r1.incident_id
    inc = db.get(Incident, r1.incident_id)
    # Existing type must be preserved
    assert inc.incident_type == "FLOOD_FLASH_FLOOD"
    # Status must route to NEEDS_REVIEW due to conflicting hazard classification
    assert inc.status == "NEEDS_REVIEW"


def test_ingest_urgency_escalation(db: Session):
    """Urgency escalates to highest known tier (CRITICAL > HIGH > MEDIUM > LOW)."""
    rep_id_1 = f"rep-test-urg-1-{uuid.uuid4().hex[:6]}"
    rep_id_2 = f"rep-test-urg-2-{uuid.uuid4().hex[:6]}"
    rep_id_3 = f"rep-test-urg-3-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        if report_id == rep_id_1:
            return build_mock_prediction(report_id, urgency="MEDIUM")
        if report_id == rep_id_2:
            return build_mock_prediction(report_id, urgency="CRITICAL")
        return build_mock_prediction(report_id, urgency="LOW")

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id_1,
        text="Water pooling near Rasulgarh underpass.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r1 = service.ingest_report(p1)
    inc = db.get(Incident, r1.incident_id)
    assert inc.urgency == "MEDIUM"

    # Escalate to CRITICAL
    p2 = RawReportCreate(
        report_id=rep_id_2,
        text="Critical situation! People drowning in Rasulgarh underpass.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=5),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    service.ingest_report(p2)
    db.refresh(inc)
    assert inc.urgency == "CRITICAL"

    # Lower urgency report (LOW) does NOT downgrade CRITICAL
    p3 = RawReportCreate(
        report_id=rep_id_3,
        text="Traffic stalled near Rasulgarh.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=10),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    service.ingest_report(p3)
    db.refresh(inc)
    assert inc.urgency == "CRITICAL"


def test_ingest_people_count_max_not_sum(db: Session):
    """People at risk count takes max(existing, new) and never sums counts."""
    rep_id_1 = f"rep-test-risk-1-{uuid.uuid4().hex[:6]}"
    rep_id_2 = f"rep-test-risk-2-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        if report_id == rep_id_1:
            return build_mock_prediction(report_id, risk_count=2)
        return build_mock_prediction(report_id, risk_count=5)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id_1,
        text="Two people trapped at Rasulgarh.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r1 = service.ingest_report(p1)

    p2 = RawReportCreate(
        report_id=rep_id_2,
        text="Around 5 people trapped at Rasulgarh.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=5),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    service.ingest_report(p2)

    inc = db.get(Incident, r1.incident_id)
    # Must be 5 (max), NOT 7 (sum)
    assert inc.people_at_risk_count == 5


def test_ingest_location_precision_refinement(db: Session):
    """Higher precision coordinates refine lower precision coordinates, but lower precision does not overwrite."""
    rep_id_1 = f"rep-test-loc-1-{uuid.uuid4().hex[:6]}"
    rep_id_2 = f"rep-test-loc-2-{uuid.uuid4().hex[:6]}"
    rep_id_3 = f"rep-test-loc-3-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        if report_id == rep_id_1:
            return build_mock_prediction(report_id, location_text="Rasulgarh", latitude=None, longitude=None, precision=LocationPrecision.UNKNOWN)
        if report_id == rep_id_2:
            return build_mock_prediction(report_id, location_text="Rasulgarh underpass GPS", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.EXACT)
        return build_mock_prediction(report_id, location_text="Rasulgarh area", latitude=20.2900, longitude=85.8200, precision=LocationPrecision.APPROXIMATE)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id_1,
        text="Water rising at Rasulgarh.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=None, longitude=None, precision=LocationPrecision.UNKNOWN),
    )
    r1 = service.ingest_report(p1)
    inc = db.get(Incident, r1.incident_id)
    assert inc.latitude is None
    assert inc.location_precision == "unknown"

    # Exact coordinates refine unknown
    p2 = RawReportCreate(
        report_id=rep_id_2,
        text="Water rising at Rasulgarh underpass pillar 4.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=5),
        location_hint=LocationHint(raw_text="Rasulgarh underpass", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.EXACT),
    )
    service.ingest_report(p2)
    db.refresh(inc)
    assert inc.latitude == 20.2961
    assert inc.longitude == 85.8245
    assert inc.location_precision == "exact"

    # Approximate coordinates do not overwrite exact
    p3 = RawReportCreate(
        report_id=rep_id_3,
        text="Water rising at Rasulgarh general area.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=10),
        location_hint=LocationHint(raw_text="Rasulgarh general", latitude=20.2900, longitude=85.8200, precision=LocationPrecision.APPROXIMATE),
    )
    service.ingest_report(p3)
    db.refresh(inc)
    assert inc.latitude == 20.2961
    assert inc.location_precision == "exact"


def test_ingest_required_response_union(db: Session):
    """Required response types form a deduplicated set union in stable canonical order."""
    rep_id_1 = f"rep-test-resp-1-{uuid.uuid4().hex[:6]}"
    rep_id_2 = f"rep-test-resp-2-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        if report_id == rep_id_1:
            return build_mock_prediction(report_id, required_response=["SEARCH_AND_RESCUE"])
        return build_mock_prediction(report_id, required_response=["MEDICAL_EMS", "SEARCH_AND_RESCUE"])

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id_1,
        text="Rescue boat required at Rasulgarh underpass.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r1 = service.ingest_report(p1)

    p2 = RawReportCreate(
        report_id=rep_id_2,
        text="Ambulance and rescue boat required at Rasulgarh underpass.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=5),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    service.ingest_report(p2)

    inc = db.get(Incident, r1.incident_id)
    assert inc.required_response == ["SEARCH_AND_RESCUE", "MEDICAL_EMS"]


def test_synthetic_and_real_strict_partition(db: Session):
    """Synthetic simulator reports cannot fuse into real-world incidents, and vice versa."""
    rep_id_real = f"rep-test-part-real-{uuid.uuid4().hex[:6]}"
    rep_id_sim = f"rep-test-part-sim-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    # Real citizen report
    p_real = RawReportCreate(
        report_id=rep_id_real,
        text="Severe flooding at Rasulgarh junction.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r_real = service.ingest_report(p_real)

    # Simulator report with identical content and location
    p_sim = RawReportCreate(
        report_id=rep_id_sim,
        text="Severe flooding at Rasulgarh junction.",
        source=SourceType.SIMULATOR,
        is_synthetic=True,
        reported_at=now + timedelta(minutes=1),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r_sim = service.ingest_report(p_sim)

    # Must be separate incidents (strict synthetic partition)
    assert r_real.incident_id != r_sim.incident_id
    assert r_sim.is_new_incident is True

    inc_real = db.get(Incident, r_real.incident_id)
    inc_sim = db.get(Incident, r_sim.incident_id)
    assert inc_real.is_synthetic is False
    assert inc_sim.is_synthetic is True


def test_candidate_horizon_cutoff_6_hours(db: Session):
    """Candidate incidents older than exactly 6 hours are not correlated."""
    rep_id_old = f"rep-test-old-{uuid.uuid4().hex[:6]}"
    rep_id_new = f"rep-test-new-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    p_old = RawReportCreate(
        report_id=rep_id_old,
        text="Flooding at Rasulgarh.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now - timedelta(hours=7),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r_old = service.ingest_report(p_old)

    # Age the incident artificially past 6 hours
    old_inc = db.get(Incident, r_old.incident_id)
    old_inc.updated_at = now - timedelta(hours=6, minutes=5)
    db.commit()

    # New report arriving now should not correlate with old incident
    p_new = RawReportCreate(
        report_id=rep_id_new,
        text="Flooding at Rasulgarh.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r_new = service.ingest_report(p_new)

    assert r_new.incident_id != r_old.incident_id
    assert r_new.is_new_incident is True


def test_idempotent_identical_report_retry(db: Session):
    """Submitting the exact same report_id and payload returns existing result without creating duplicate records."""
    rep_id = f"rep-test-idem-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    payload = RawReportCreate(
        report_id=rep_id,
        text="Flash flood warning near Rasulgarh underpass.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=datetime.now(timezone.utc),
    )

    res1 = service.ingest_report(payload)
    res2 = service.ingest_report(payload)

    assert res1.report_id == res2.report_id
    assert res1.incident_id == res2.incident_id
    assert res2.is_new_incident is False

    # Verify no duplicate raw_reports
    count = db.query(RawReport).filter_by(report_id=rep_id).count()
    assert count == 1


def test_same_report_id_different_payload_conflict(db: Session):
    """Submitting same report_id with different payload raises REPORT_ID_CONFLICT and does not overwrite."""
    rep_id = f"rep-test-conf-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id,
        text="Original text for report.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
    )
    service.ingest_report(p1)

    p2 = RawReportCreate(
        report_id=rep_id,
        text="Altered text with malicious modification.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
    )

    with pytest.raises(AppException) as exc_info:
        service.ingest_report(p2)

    assert exc_info.value.code == "REPORT_ID_CONFLICT"
    assert exc_info.value.status_code == 400

    # Ensure original report remains intact
    raw = db.get(RawReport, rep_id)
    assert raw.text == "Original text for report."


def test_interrupted_raw_report_resumes_processing(db: Session):
    """If a raw report exists but lacks an incident link (interrupted flow), re-ingestion resumes Phase B."""
    rep_id = f"rep-test-resum-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    # Manually insert an unlinked raw report
    raw = RawReport(
        report_id=rep_id,
        text="Interrupted dispatch report text.",
        source="manual",
        is_synthetic=False,
        reported_at=now,
    )
    db.add(raw)
    db.commit()

    # Call ingest_report with matching payload
    payload = RawReportCreate(
        report_id=rep_id,
        text="Interrupted dispatch report text.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
    )
    result = service.ingest_report(payload)

    assert result.report_id == rep_id
    assert result.is_new_incident is True

    # Link now exists
    link = db.query(IncidentReportLink).filter_by(report_id=rep_id).first()
    assert link is not None


def test_raw_report_persisted_if_ml_analyzer_fails_with_bounded_recovery(db: Session):
    """When ML analysis fails, raw report is committed and bounded recovery creates NEEDS_REVIEW incident."""
    rep_id = f"rep-test-fail-{uuid.uuid4().hex[:6]}"

    def failing_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> dict:
        raise RuntimeError("Model runtime crashed")

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=failing_analyzer))

    payload = RawReportCreate(
        report_id=rep_id,
        text="Disaster dispatch text during model crash.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=datetime.now(timezone.utc),
        location_hint=LocationHint(raw_text="Khandagiri", precision=LocationPrecision.APPROXIMATE),
    )

    result = service.ingest_report(payload)

    assert result.processing_status == ProcessingStatus.FAILED

    # Raw report MUST be safely preserved in database
    raw = db.get(RawReport, rep_id)
    assert raw is not None
    assert raw.text == payload.text

    # Incident created in NEEDS_REVIEW status
    inc = db.get(Incident, result.incident_id)
    assert inc is not None
    assert inc.status == "NEEDS_REVIEW"
    assert float(inc.priority_score) == 50.00
    assert inc.priority_level == "MEDIUM"


def test_human_override_and_status_preservation(db: Session):
    """Incident with VERIFIED status or active human override is preserved from automatic downgrades."""
    rep_id_1 = f"rep-test-over-1-{uuid.uuid4().hex[:6]}"
    rep_id_2 = f"rep-test-over-2-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id, urgency="LOW")

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id_1,
        text="Gas leak report at Rasulgarh.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r1 = service.ingest_report(p1)

    # Operator marks incident VERIFIED and applies override
    inc = db.get(Incident, r1.incident_id)
    inc.status = "VERIFIED"
    inc.human_override = {
        "active": True,
        "updated_by": "operator_42",
        "reason": "Confirmed by on-site crew",
    }
    db.commit()

    # Second report arrives with UNCERTAIN or conflicting signal
    p2 = RawReportCreate(
        report_id=rep_id_2,
        text="Gas leak report at Rasulgarh update.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=5),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    service.ingest_report(p2)

    db.refresh(inc)
    # Operator status and override must NOT be downgraded or overwritten
    assert inc.status == "VERIFIED"
    assert inc.human_override["active"] is True


def test_ingest_partial_ml_routes_to_needs_review_without_extra_penalty(db: Session):
    """
    Any MLPredictionOutput with processing_status == PARTIAL routes incident to NEEDS_REVIEW.
    processing_status itself remains PARTIAL in MLPrediction and response result.
    Deterministic priority scoring applies normal calculation without extra penalties.
    """
    rep_id = f"rep-test-partial-{uuid.uuid4().hex[:6]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        # Build mock prediction with PARTIAL status and high confidence (0.85)
        return build_mock_prediction(
            report_id=report_id,
            incident_type="FLOOD_FLASH_FLOOD",
            urgency="HIGH",
            risk_count=2,
            location_text="Rasulgarh underpass",
            latitude=20.2961,
            longitude=85.8245,
            processing_status=ProcessingStatus.PARTIAL,
            overall_confidence=0.85,
        )

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    payload = RawReportCreate(
        report_id=rep_id,
        text="Partial dispatch text with incomplete details near Rasulgarh.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=datetime.now(timezone.utc),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )

    result = service.ingest_report(payload)

    # 1. Verification of processing_status
    assert result.processing_status == ProcessingStatus.PARTIAL
    assert result.report_id == rep_id
    assert result.is_new_incident is True

    # 2. Verification of incident status
    inc = db.get(Incident, result.incident_id)
    assert inc is not None
    assert inc.status == "NEEDS_REVIEW"

    # 3. Verification that MLPrediction record retains PARTIAL
    pred_rec = db.get(MLPrediction, rep_id) or service.repo.get_ml_prediction(db, rep_id)
    assert pred_rec is not None
    assert pred_rec.processing_status == "PARTIAL"

    # 4. Priority scoring check: pure engine formula with NO additional penalty
    # Expected: Urgency HIGH (26.25) + Risk 2 (19.20) + Corrob 1 (7.20) + Hazard FLOOD (12.75) = 65.40
    expected_priority = calculate_priority(
        incident=inc,
        urgency="HIGH",
        people_at_risk_count=2,
        independent_sources=1,
        corroboration_score=0.36,
        incident_type="FLOOD_FLASH_FLOOD",
        status="NEEDS_REVIEW",
        ml_confidence=0.85,
    )
    assert float(inc.priority_score) == expected_priority.score
    assert inc.priority_level == expected_priority.level.value
    # Assert no penalty was applied for PARTIAL or NEEDS_REVIEW
    assert not any("PARTIAL" in m for m in expected_priority.modifiers_applied)
    assert not any("NEEDS_REVIEW" in m for m in expected_priority.modifiers_applied)


def test_ingest_partial_ml_fused_with_active_incident_routes_to_needs_review(db: Session):
    """Fusing a PARTIAL ML report into an unprotected ACTIVE incident transitions it to NEEDS_REVIEW."""
    rep_id_1 = f"rep-test-pact-1-{uuid.uuid4().hex[:6]}"
    rep_id_2 = f"rep-test-pact-2-{uuid.uuid4().hex[:6]}"

    def initial_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id, processing_status=ProcessingStatus.SUCCESS)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=initial_analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id_1,
        text="Initial active flooding event at Rasulgarh.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r1 = service.ingest_report(p1)

    inc = db.get(Incident, r1.incident_id)
    assert inc.status == "ACTIVE"

    # Second report arrives with PARTIAL status
    def partial_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id, processing_status=ProcessingStatus.PARTIAL)

    service_partial = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=partial_analyzer))
    p2 = RawReportCreate(
        report_id=rep_id_2,
        text="Second flood update near Rasulgarh with incomplete details.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=5),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r2 = service_partial.ingest_report(p2)

    db.refresh(inc)
    assert r2.incident_id == inc.incident_id
    assert r2.processing_status == ProcessingStatus.PARTIAL
    # Incomplete extraction routes incident to NEEDS_REVIEW
    assert inc.status == "NEEDS_REVIEW"


def test_ingest_partial_ml_fused_with_human_override_preserves_status(db: Session):
    """Fusing a PARTIAL ML report into an incident with active human override preserves existing status."""
    rep_id_1 = f"rep-test-povr-1-{uuid.uuid4().hex[:6]}"
    rep_id_2 = f"rep-test-povr-2-{uuid.uuid4().hex[:6]}"

    def initial_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id, processing_status=ProcessingStatus.SUCCESS)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=initial_analyzer))

    now = datetime.now(timezone.utc)
    p1 = RawReportCreate(
        report_id=rep_id_1,
        text="Initial active flooding event at Rasulgarh underpass.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now,
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r1 = service.ingest_report(p1)

    # Operator applies human override on active incident
    inc = db.get(Incident, r1.incident_id)
    assert inc.status == "ACTIVE"
    inc.human_override = {
        "active": True,
        "updated_by": "operator_chief",
        "reason": "Tactical decision to keep active",
    }
    db.commit()

    # Second report arrives with PARTIAL status
    def partial_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id, processing_status=ProcessingStatus.PARTIAL)

    service_partial = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=partial_analyzer))
    p2 = RawReportCreate(
        report_id=rep_id_2,
        text="Second flood update near Rasulgarh underpass with partial information.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=now + timedelta(minutes=5),
        location_hint=LocationHint(raw_text="Rasulgarh", latitude=20.2961, longitude=85.8245, precision=LocationPrecision.APPROXIMATE),
    )
    r2 = service_partial.ingest_report(p2)

    db.refresh(inc)
    assert r2.incident_id == inc.incident_id
    assert r2.processing_status == ProcessingStatus.PARTIAL
    # Protected by active human override: must remain ACTIVE, not changed to NEEDS_REVIEW
    assert inc.status == "ACTIVE"
    assert inc.human_override["active"] is True


def test_ingest_omitted_report_id_generates_canonical_id(db: Session):
    """When report_id is omitted, backend generates rep-<uuid> and uses it consistently."""
    generated_id: Optional[str] = None
    try:
        def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
            return build_mock_prediction(report_id)

        service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

        payload = RawReportCreate(
            text="Distress dispatch report with omitted ID.",
            source=SourceType.MANUAL,
            is_synthetic=False,
            reported_at=datetime.now(timezone.utc),
        )

        assert payload.report_id is not None
        assert payload.report_id.startswith("rep-")
        generated_id = payload.report_id

        result = service.ingest_report(payload)

        assert result.report_id == generated_id
        assert db.get(RawReport, generated_id) is not None
        assert service.repo.get_ml_prediction(db, generated_id) is not None
        assert service.repo.get_incident_link_by_report_id(db, generated_id) is not None
    finally:
        if generated_id:
            db.rollback()
            db.execute(text("DELETE FROM incident_reports WHERE report_id = :rid"), {"rid": generated_id})
            db.execute(text("DELETE FROM ml_predictions WHERE report_id = :rid"), {"rid": generated_id})
            db.execute(text("DELETE FROM raw_reports WHERE report_id = :rid"), {"rid": generated_id})
            db.commit()


def test_ingest_empty_report_id_generates_canonical_id(db: Session):
    """When report_id is empty string or whitespace, backend generates rep-<uuid>."""
    generated_id: Optional[str] = None
    try:
        def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
            return build_mock_prediction(report_id)

        service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

        payload = RawReportCreate(
            report_id="   ",
            text="Distress dispatch report with whitespace ID.",
            source=SourceType.MANUAL,
            is_synthetic=False,
            reported_at=datetime.now(timezone.utc),
        )

        assert payload.report_id is not None
        assert payload.report_id.startswith("rep-")
        assert payload.report_id.strip() != ""
        generated_id = payload.report_id

        result = service.ingest_report(payload)

        assert result.report_id == generated_id
        assert db.get(RawReport, generated_id) is not None
        assert service.repo.get_ml_prediction(db, generated_id) is not None
        assert service.repo.get_incident_link_by_report_id(db, generated_id) is not None
    finally:
        if generated_id:
            db.rollback()
            db.execute(text("DELETE FROM incident_reports WHERE report_id = :rid"), {"rid": generated_id})
            db.execute(text("DELETE FROM ml_predictions WHERE report_id = :rid"), {"rid": generated_id})
            db.execute(text("DELETE FROM raw_reports WHERE report_id = :rid"), {"rid": generated_id})
            db.commit()


def test_ingest_supplied_report_id_preserved(db: Session):
    """When client supplies a non-empty report_id, it is preserved across all tables."""
    rep_id = f"rep-test-supplied-{uuid.uuid4().hex[:8]}"

    def analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        return build_mock_prediction(report_id)

    service = IngestionService(db=db, ml_adapter=MLAdapter(analyzer=analyzer))

    payload = RawReportCreate(
        report_id=rep_id,
        text="Report with client-supplied custom ID.",
        source=SourceType.MANUAL,
        is_synthetic=False,
        reported_at=datetime.now(timezone.utc),
    )

    result = service.ingest_report(payload)

    assert result.report_id == rep_id
    assert db.get(RawReport, rep_id) is not None
    assert service.repo.get_ml_prediction(db, rep_id) is not None
    assert service.repo.get_incident_link_by_report_id(db, rep_id) is not None


def test_synthetic_guardrail_simulator_rejected_when_not_synthetic():
    """source == 'simulator' requires is_synthetic == True; False raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        RawReportCreate(
            text="Simulator dispatch report without synthetic flag.",
            source=SourceType.SIMULATOR,
            is_synthetic=False,
            reported_at=datetime.now(timezone.utc),
        )
    assert "Reports with source 'simulator' must have is_synthetic set to True." in str(exc_info.value)


def test_synthetic_guardrail_manual_rejected_when_synthetic():
    """source == 'manual' requires is_synthetic == False; True raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        RawReportCreate(
            text="Manual citizen call report with synthetic flag true.",
            source=SourceType.MANUAL,
            is_synthetic=True,
            reported_at=datetime.now(timezone.utc),
        )
    assert "Reports with source 'manual' must have is_synthetic set to False." in str(exc_info.value)

