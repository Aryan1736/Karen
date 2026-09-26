"""
Karen's Ear — Incident REST API Integration Tests
Tests:
- GET /incidents (no filter, filtering by status/level, pagination, counts, priority ordering)
- GET /incidents/{id} (canonical nested incident, source reports, audit trail, 404)
- POST /incidents/{id}/review (valid transitions, invalid transitions, same status, operator identity, notes length, priority recalculation)
- POST /incidents/{id}/override (allowed fields, validation, reason length, human_override snapshot, priority recalculation)
- Human override protection against subsequent ingestion
- GET /incidents/{id}/timeline (event types, ordering, no citizen raw-text leak)
"""
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Generator
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.db.session import SessionLocal, get_db
from backend.app.main import app
from backend.app.models.audit import AuditLog
from backend.app.models.incident import Incident
from backend.app.models.link import IncidentReportLink
from backend.app.models.ml import MLPrediction
from backend.app.models.priority import PriorityCalculation
from backend.app.models.report import RawReport
from backend.app.schemas.common import ProcessingStatus
from backend.app.schemas.ml import (
    LocationPrediction,
    MLPredictionOutput,
    ResponseNeed,
    RiskPrediction,
    TypePrediction,
    UrgencyPrediction,
)
from backend.app.schemas.report import RawReportCreate
from backend.app.services.ingestion import IngestionService
from backend.app.services.ml_adapter import MLAdapter


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides an isolated database session and cleans up test records."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(text("DELETE FROM audit_logs WHERE incident_id LIKE 'inc-test-%'"))
        session.execute(text("DELETE FROM priority_calculations WHERE incident_id LIKE 'inc-test-%'"))
        session.execute(text("DELETE FROM incident_reports WHERE incident_id LIKE 'inc-test-%' OR report_id LIKE 'rep-test-%'"))
        session.execute(text("DELETE FROM ml_predictions WHERE report_id LIKE 'rep-test-%'"))
        session.execute(text("DELETE FROM raw_reports WHERE report_id LIKE 'rep-test-%'"))
        session.execute(text("DELETE FROM incidents WHERE incident_id LIKE 'inc-test-%'"))
        session.commit()
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient fixture with get_db dependency override."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def seed_incident(
    db: Session,
    incident_id: str,
    status: str = "ACTIVE",
    priority_score: float = 50.0,
    priority_level: str = "MEDIUM",
    incident_type: str = "FLOOD_FLASH_FLOOD",
    urgency: str = "MEDIUM",
    people_at_risk_count: int = 2,
    location_text: str = "Patia Square",
    human_override: dict | None = None,
) -> Incident:
    """Helper to insert an Incident record."""
    inc = Incident(
        incident_id=incident_id,
        status=status,
        incident_type=incident_type,
        urgency=urgency,
        location_text=location_text,
        latitude=20.35,
        longitude=85.82,
        location_precision="approximate",
        people_at_risk_count=people_at_risk_count,
        required_response=["SEARCH_AND_RESCUE"],
        priority_score=priority_score,
        priority_level=priority_level,
        corroboration_score=0.36,
        report_count=1,
        independent_source_count=1,
        human_override=human_override or {"active": False},
        is_synthetic=True,
    )
    db.add(inc)
    db.flush()
    return inc


def seed_report_and_link(
    db: Session,
    incident_id: str,
    report_id: str,
    text_content: str = "Flood waters rising",
    rel_type: str = "INITIAL",
    overall_confidence: float = 0.85,
) -> tuple[RawReport, IncidentReportLink, MLPrediction]:
    """Helper to seed raw report, ML prediction, and fusion link."""
    now = datetime.now(timezone.utc)
    rep = RawReport(
        report_id=report_id,
        text=text_content,
        source="simulator",
        is_synthetic=True,
        reported_at=now,
        location_hint={"raw_text": "Patia", "latitude": 20.35, "longitude": 85.82, "precision": "approximate"},
        metadata_={"test": True},
    )
    db.add(rep)

    pred = MLPrediction(
        prediction_id=f"pred-{uuid.uuid4()}",
        report_id=report_id,
        model_version="test-v1",
        incident_type={"label": "FLOOD_FLASH_FLOOD", "confidence": 0.90},
        urgency={"label": "MEDIUM", "confidence": 0.80},
        location={"text": "Patia", "latitude": 20.35, "longitude": 85.82, "precision": "approximate", "confidence": 0.85},
        people_at_risk={"count": 2, "confidence": 0.75},
        required_response=[{"type": "SEARCH_AND_RESCUE", "confidence": 0.9}],
        entities=[],
        embedding=None,
        overall_confidence=overall_confidence,
        processing_status="SUCCESS",
        warnings=[],
    )
    db.add(pred)

    link = IncidentReportLink(
        id=f"link-{uuid.uuid4()}",
        incident_id=incident_id,
        report_id=report_id,
        relationship_type=rel_type,
        similarity_score=0.88 if rel_type != "INITIAL" else None,
        fused_at=now,
    )
    db.add(link)
    db.flush()
    return rep, link, pred


def seed_priority_calc(
    db: Session,
    incident_id: str,
    score: float,
    level: str,
    explanation: str = "Test calculation",
    calc_version: str = "v1.0-deterministic",
) -> PriorityCalculation:
    """Helper to insert a priority calculation."""
    pcalc = PriorityCalculation(
        calc_id=f"calc-{uuid.uuid4()}",
        incident_id=incident_id,
        priority_score=score,
        priority_level=level,
        factors=[{"factor": "Urgency (Life-Safety)", "value": "MEDIUM", "weight": 0.35, "contribution": 14.0}],
        explanation=explanation,
        calc_version=calc_version,
    )
    db.add(pcalc)
    db.flush()
    return pcalc


# ==============================================================================
# 1. GET /incidents tests
# ==============================================================================

def test_get_incidents_no_filters_returns_all_statuses(client: TestClient, db_session: Session):
    """If status is omitted, all statuses must be returned."""
    seed_incident(db_session, "inc-test-active-1", status="ACTIVE", priority_score=85.0, priority_level="CRITICAL")
    seed_incident(db_session, "inc-test-review-1", status="NEEDS_REVIEW", priority_score=65.0, priority_level="HIGH")
    seed_incident(db_session, "inc-test-resolved-1", status="RESOLVED", priority_score=0.0, priority_level="LOW")
    seed_incident(db_session, "inc-test-false-1", status="FALSE_REPORT", priority_score=0.0, priority_level="LOW")
    db_session.commit()

    res = client.get("/incidents")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    incident_ids = [inc["incident_id"] for inc in data["data"]["incidents"]]
    assert "inc-test-active-1" in incident_ids
    assert "inc-test-review-1" in incident_ids
    assert "inc-test-resolved-1" in incident_ids
    assert "inc-test-false-1" in incident_ids


def test_get_incidents_status_and_level_filtering(client: TestClient, db_session: Session):
    """Filter by comma-separated status and level."""
    seed_incident(db_session, "inc-test-f-1", status="ACTIVE", priority_score=90.0, priority_level="CRITICAL")
    seed_incident(db_session, "inc-test-f-2", status="VERIFIED", priority_score=85.0, priority_level="CRITICAL")
    seed_incident(db_session, "inc-test-f-3", status="ACTIVE", priority_score=40.0, priority_level="MEDIUM")
    seed_incident(db_session, "inc-test-f-4", status="RESOLVED", priority_score=0.0, priority_level="LOW")
    db_session.commit()

    # Filter status=ACTIVE,VERIFIED and level=CRITICAL
    res = client.get("/incidents?status=ACTIVE,VERIFIED&level=CRITICAL")
    assert res.status_code == 200
    incidents = res.json()["data"]["incidents"]
    ids = [inc["incident_id"] for inc in incidents]
    assert "inc-test-f-1" in ids
    assert "inc-test-f-2" in ids
    assert "inc-test-f-3" not in ids
    assert "inc-test-f-4" not in ids


def test_get_incidents_ordering_and_pagination(client: TestClient, db_session: Session):
    """Verify priority_score DESC ordering, limit, offset, and counts."""
    seed_incident(db_session, "inc-test-ord-1", status="ACTIVE", priority_score=30.0, priority_level="LOW")
    seed_incident(db_session, "inc-test-ord-2", status="ACTIVE", priority_score=95.0, priority_level="CRITICAL")
    seed_incident(db_session, "inc-test-ord-3", status="ACTIVE", priority_score=70.0, priority_level="HIGH")
    seed_incident(db_session, "inc-test-ord-4", status="ACTIVE", priority_score=85.0, priority_level="CRITICAL")
    db_session.commit()

    # Query with limit 2, offset 0
    res = client.get("/incidents?status=ACTIVE&limit=2&offset=0")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["incidents"]) == 2
    # First should be 95.0, second 85.0
    assert data["incidents"][0]["incident_id"] == "inc-test-ord-2"
    assert data["incidents"][1]["incident_id"] == "inc-test-ord-4"
    # total_count before pagination is 4
    assert data["total_count"] == 4
    # critical_count before pagination matching status=ACTIVE is 2
    assert data["critical_count"] == 2

    # Query next page
    res_p2 = client.get("/incidents?status=ACTIVE&limit=2&offset=2")
    data_p2 = res_p2.json()["data"]
    assert len(data_p2["incidents"]) == 2
    assert data_p2["incidents"][0]["incident_id"] == "inc-test-ord-3"
    assert data_p2["incidents"][1]["incident_id"] == "inc-test-ord-1"


def test_get_incidents_source_report_ids_and_latest_ml_confidence(client: TestClient, db_session: Session):
    """Verify source_report_ids in fusion order and latest ML confidence exposed."""
    inc = seed_incident(db_session, "inc-test-ml-1", status="ACTIVE")
    seed_report_and_link(db_session, "inc-test-ml-1", "rep-test-ml-1", rel_type="INITIAL", overall_confidence=0.70)
    seed_report_and_link(db_session, "inc-test-ml-1", "rep-test-ml-2", rel_type="CORROBORATING", overall_confidence=0.92)
    seed_priority_calc(db_session, "inc-test-ml-1", score=inc.priority_score, level=inc.priority_level, explanation="Calc 1")
    db_session.commit()

    res = client.get("/incidents?status=ACTIVE")
    assert res.status_code == 200
    matching = [i for i in res.json()["data"]["incidents"] if i["incident_id"] == "inc-test-ml-1"]
    assert len(matching) == 1
    dto = matching[0]
    # source_report_ids should have both in order
    assert dto["source_report_ids"] == ["rep-test-ml-1", "rep-test-ml-2"]
    # latest ML confidence is from rep-test-ml-2 (0.92)
    assert dto["ml_confidence"]["overall"] == 0.92


# ==============================================================================
# 2. GET /incidents/{id} tests
# ==============================================================================

def test_get_incident_detail_success(client: TestClient, db_session: Session):
    """GET /incidents/{id} returns canonical Incident, source_reports, and audit_trail."""
    seed_incident(db_session, "inc-test-dtl-1", status="ACTIVE", priority_score=80.0, priority_level="CRITICAL")
    seed_report_and_link(db_session, "inc-test-dtl-1", "rep-test-dtl-1")
    audit = AuditLog(
        override_id="ovr-test-dtl-1",
        incident_id="inc-test-dtl-1",
        operator_id="op_tester",
        field="urgency",
        previous_value="MEDIUM",
        new_value="CRITICAL",
        reason="Field visual confirmation of high water",
    )
    db_session.add(audit)
    db_session.commit()

    res = client.get("/incidents/inc-test-dtl-1")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["incident"]["incident_id"] == "inc-test-dtl-1"
    assert len(data["source_reports"]) == 1
    assert data["source_reports"][0]["report_id"] == "rep-test-dtl-1"
    assert len(data["audit_trail"]) == 1
    assert data["audit_trail"][0]["override_id"] == "ovr-test-dtl-1"


def test_get_incident_detail_404_canonical_envelope(client: TestClient):
    """Unknown incident returns HTTP 404 with canonical error envelope."""
    res = client.get("/incidents/inc-unknown-999")
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


# ==============================================================================
# 3. POST /incidents/{id}/review tests
# ==============================================================================

def test_review_operator_identity_header_and_body_matching(client: TestClient, db_session: Session):
    """Accepts matching X-Operator-Id and operator_id."""
    seed_incident(db_session, "inc-test-rev-id-1", status="ACTIVE")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-id-1/review",
        json={"operator_id": "op_alpha", "target_status": "VERIFIED", "notes": "Verified on ground"},
        headers={"X-Operator-Id": "op_alpha"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["incident"]["status"] == "VERIFIED"


def test_review_operator_identity_conflict_rejected(client: TestClient, db_session: Session):
    """Differing X-Operator-Id and operator_id returns 422 OPERATOR_ID_MISMATCH."""
    seed_incident(db_session, "inc-test-rev-id-2", status="ACTIVE")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-id-2/review",
        json={"operator_id": "op_body", "target_status": "VERIFIED", "notes": "Verified on ground"},
        headers={"X-Operator-Id": "op_header"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "OPERATOR_ID_MISMATCH"


def test_review_missing_operator_rejected(client: TestClient, db_session: Session):
    """Missing operator_id in both body and header rejected with 422."""
    seed_incident(db_session, "inc-test-rev-id-3", status="ACTIVE")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-id-3/review",
        json={"target_status": "VERIFIED", "notes": "Verified on ground"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_review_short_notes_rejected(client: TestClient, db_session: Session):
    """Review notes < 5 non-whitespace chars rejected."""
    seed_incident(db_session, "inc-test-rev-notes", status="ACTIVE")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-notes/review",
        json={"operator_id": "op1", "target_status": "VERIFIED", "notes": "  ok "},
    )
    assert res.status_code == 422


def test_review_same_status_rejected(client: TestClient, db_session: Session):
    """No-op transition to same status rejected."""
    seed_incident(db_session, "inc-test-rev-same", status="ACTIVE")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-same/review",
        json={"operator_id": "op1", "target_status": "ACTIVE", "notes": "No change needed"},
    )
    assert res.status_code == 422


def test_review_invalid_transition_resolved_to_escalated_rejected(client: TestClient, db_session: Session):
    """RESOLVED cannot transition directly to ESCALATED."""
    seed_incident(db_session, "inc-test-rev-inv-1", status="RESOLVED")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-inv-1/review",
        json={"operator_id": "op1", "target_status": "ESCALATED", "notes": "Attempting jump"},
    )
    assert res.status_code == 422


def test_review_false_report_terminal_rejected(client: TestClient, db_session: Session):
    """FALSE_REPORT has no outgoing transitions."""
    seed_incident(db_session, "inc-test-rev-term", status="FALSE_REPORT")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-term/review",
        json={"operator_id": "op1", "target_status": "ACTIVE", "notes": "Reopening false report"},
    )
    assert res.status_code == 422


def test_review_transition_to_internal_status_rejected(client: TestClient, db_session: Session):
    """Cannot transition to NEW or ANALYZING."""
    seed_incident(db_session, "inc-test-rev-intern", status="ACTIVE")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-intern/review",
        json={"operator_id": "op1", "target_status": "NEW", "notes": "Resetting status"},
    )
    assert res.status_code == 422


def test_review_verified_applies_priority_boost(client: TestClient, db_session: Session):
    """VERIFIED status transition applies +10 status modifier to priority."""
    inc = seed_incident(db_session, "inc-test-rev-ver", status="ACTIVE", priority_score=50.0, priority_level="MEDIUM")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-ver/review",
        json={"operator_id": "op_ver", "target_status": "VERIFIED", "notes": "Ground team confirmed flooding"},
    )
    assert res.status_code == 200
    dto = res.json()["data"]["incident"]
    assert dto["status"] == "VERIFIED"
    # Verification adds +10 to score
    assert dto["priority"]["score"] >= 60.0


def test_review_escalated_applies_surge_boost(client: TestClient, db_session: Session):
    """ESCALATED status transition applies +15 status modifier."""
    inc = seed_incident(db_session, "inc-test-rev-esc", status="ACTIVE", priority_score=50.0, priority_level="MEDIUM")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-esc/review",
        json={"operator_id": "op_esc", "target_status": "ESCALATED", "notes": "Water rising above second floor"},
    )
    assert res.status_code == 200
    dto = res.json()["data"]["incident"]
    assert dto["status"] == "ESCALATED"
    assert dto["priority"]["score"] >= 65.0


def test_review_resolved_forces_priority_zero(client: TestClient, db_session: Session):
    """RESOLVED forces priority to 0.00 (LOW)."""
    seed_incident(db_session, "inc-test-rev-res", status="ACTIVE", priority_score=85.0, priority_level="CRITICAL")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-res/review",
        json={"operator_id": "op_res", "target_status": "RESOLVED", "notes": "Rescue complete and waters receded"},
    )
    assert res.status_code == 200
    dto = res.json()["data"]["incident"]
    assert dto["status"] == "RESOLVED"
    assert dto["priority"]["score"] == 0.0
    assert dto["priority"]["level"] == "LOW"


def test_review_false_report_forces_priority_zero(client: TestClient, db_session: Session):
    """FALSE_REPORT forces priority to 0.00 (LOW) and sets status FALSE_REPORT."""
    seed_incident(db_session, "inc-test-rev-fls", status="NEEDS_REVIEW", priority_score=50.0, priority_level="MEDIUM")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-fls/review",
        json={"operator_id": "op_fls", "target_status": "FALSE_REPORT", "notes": "Verified as prank call"},
    )
    assert res.status_code == 200
    dto = res.json()["data"]["incident"]
    assert dto["status"] == "FALSE_REPORT"
    assert dto["priority"]["score"] == 0.0
    assert dto["priority"]["level"] == "LOW"


def test_review_reopen_resolved_recalculates_priority(client: TestClient, db_session: Session):
    """Reopening RESOLVED -> ACTIVE recalculates priority from incident facts without forcing 0."""
    seed_incident(
        db_session,
        "inc-test-rev-reopen",
        status="RESOLVED",
        priority_score=0.0,
        priority_level="LOW",
        urgency="HIGH",
        incident_type="FLOOD_FLASH_FLOOD",
        people_at_risk_count=3,
    )
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-rev-reopen/review",
        json={"operator_id": "op_reopen", "target_status": "ACTIVE", "notes": "Secondary levee breach reported"},
    )
    assert res.status_code == 200
    dto = res.json()["data"]["incident"]
    assert dto["status"] == "ACTIVE"
    # Recalculated from HIGH urgency and 3 people: must be > 0.0
    assert dto["priority"]["score"] > 50.0


# ==============================================================================
# 4. POST /incidents/{id}/override tests
# ==============================================================================

def test_override_urgency_updates_snapshot_and_recalculates_priority(client: TestClient, db_session: Session):
    """Urgency override updates human_override snapshot and reruns priority calculation."""
    seed_incident(db_session, "inc-test-ovr-urg", status="ACTIVE", urgency="LOW", priority_score=20.0, priority_level="LOW")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-ovr-urg/override",
        json={
            "operator_id": "op_ovr",
            "field": "urgency",
            "new_value": "CRITICAL",
            "reason": "Direct visual CCTV confirmation of trapped civilians",
        },
    )
    assert res.status_code == 200
    data = res.json()["data"]
    inc = data["incident"]
    assert inc["urgency"] == "CRITICAL"
    assert inc["human_override"]["active"] is True
    assert inc["human_override"]["updated_by"] == "op_ovr"
    assert inc["human_override"]["reason"] == "Direct visual CCTV confirmation of trapped civilians"
    # Priority should be elevated due to CRITICAL urgency
    assert inc["priority"]["score"] > 60.0


def test_override_direct_priority_score_derives_level(client: TestClient, db_session: Session):
    """Direct priority_score override sets score and derives priority_level."""
    seed_incident(db_session, "inc-test-ovr-score", status="ACTIVE", priority_score=25.0, priority_level="LOW")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-ovr-score/override",
        json={
            "operator_id": "op_score",
            "field": "priority_score",
            "new_value": 92.5,
            "reason": "Commander directive to elevate to maximum triage queue",
        },
    )
    assert res.status_code == 200
    inc = res.json()["data"]["incident"]
    assert inc["priority"]["score"] == 92.5
    assert inc["priority"]["level"] == "CRITICAL"


def test_override_direct_priority_level_rejected(client: TestClient, db_session: Session):
    """Direct priority_level override is explicitly rejected."""
    seed_incident(db_session, "inc-test-ovr-lvl", status="ACTIVE")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-ovr-lvl/override",
        json={
            "operator_id": "op1",
            "field": "priority_level",
            "new_value": "CRITICAL",
            "reason": "Attempting direct priority_level override",
        },
    )
    assert res.status_code == 422


def test_override_unsupported_field_rejected(client: TestClient, db_session: Session):
    """Override of unsupported field rejected with 422."""
    seed_incident(db_session, "inc-test-ovr-bad", status="ACTIVE")
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-ovr-bad/override",
        json={
            "operator_id": "op1",
            "field": "report_count",
            "new_value": 99,
            "reason": "Invalid field override attempt",
        },
    )
    assert res.status_code == 422


def test_override_location_and_required_response_validation(client: TestClient, db_session: Session):
    """Location and required_response override validations and canonical ordering."""
    seed_incident(db_session, "inc-test-ovr-loc", status="ACTIVE")
    db_session.commit()

    # Location override
    res_loc = client.post(
        "/incidents/inc-test-ovr-loc/override",
        json={
            "operator_id": "op_loc",
            "field": "location",
            "new_value": {
                "text": "Rasulgarh Flyover",
                "latitude": 20.2961,
                "longitude": 85.8245,
                "precision": "exact",
            },
            "reason": "Pinpointed via GPS vehicle locator",
        },
    )
    assert res_loc.status_code == 200
    inc = res_loc.json()["data"]["incident"]
    assert inc["location"]["text"] == "Rasulgarh Flyover"
    assert inc["location"]["precision"] == "exact"

    # Required response override (deduplication and canonical ordering)
    res_resp = client.post(
        "/incidents/inc-test-ovr-loc/override",
        json={
            "operator_id": "op_loc",
            "field": "required_response",
            "new_value": ["FIRE_HAZMAT", "SEARCH_AND_RESCUE", "FIRE_HAZMAT"],
            "reason": "Need Hazmat team on site alongside search and rescue",
        },
    )
    assert res_resp.status_code == 200
    inc_resp = res_resp.json()["data"]["incident"]
    # SEARCH_AND_RESCUE comes before FIRE_HAZMAT in canonical order
    assert inc_resp["required_response"] == ["SEARCH_AND_RESCUE", "FIRE_HAZMAT"]


def test_override_audit_trail_recorded(client: TestClient, db_session: Session):
    """Verify previous_value and new_value recorded in audit trail."""
    seed_incident(db_session, "inc-test-ovr-audit", status="ACTIVE", people_at_risk_count=1)
    db_session.commit()

    res = client.post(
        "/incidents/inc-test-ovr-audit/override",
        json={
            "operator_id": "op_cas",
            "field": "people_at_risk_count",
            "new_value": 5,
            "reason": "Casualty count updated from hospital radio dispatch",
        },
    )
    assert res.status_code == 200
    audit = res.json()["data"]["audit"]
    assert audit["field"] == "people_at_risk_count"
    assert audit["previous_value"] == 1
    assert audit["new_value"] == 5
    assert audit["reason"] == "Casualty count updated from hospital radio dispatch"


# ==============================================================================
# 5. Human Override Protection Against Ingestion
# ==============================================================================

def test_human_override_protects_against_subsequent_ingestion(client: TestClient, db_session: Session):
    """
    When human_override['active'] is True, automated report ingestion
    CANNOT overwrite operator-controlled fields (urgency, incident_type, people_at_risk, location, required_response, priority).
    """
    # Create incident with human override active and overridden priority
    inc = seed_incident(
        db_session,
        "inc-test-ho-prot",
        status="ACTIVE",
        urgency="CRITICAL",
        incident_type="STRUCTURAL_COLLAPSE",
        people_at_risk_count=10,
        location_text="Locked Human Location",
        priority_score=95.0,
        priority_level="CRITICAL",
        human_override={
            "active": True,
            "updated_by": "op_lead",
            "updated_at": "2026-09-26T12:00:00Z",
            "reason": "Locked by tactical commander",
            "priority_overridden": True,
        },
    )
    # Seed initial report to enable correlation
    seed_report_and_link(db_session, "inc-test-ho-prot", "rep-test-ho-1", text_content="Severe collapse at Rasulgarh")
    db_session.commit()

    # Now ingest a new report through IngestionService with lower urgency / different hazard
    mock_ml = MLAdapter(
        analyzer=lambda text, report_id, loc_hint: MLPredictionOutput(
            report_id=report_id,
            model_version="test-ml",
            incident_type=TypePrediction(label="FLOOD_FLASH_FLOOD", confidence=0.9),
            urgency=UrgencyPrediction(label="LOW", confidence=0.8),
            location=LocationPrediction(text="Automated New Loc", latitude=20.35, longitude=85.82, precision="exact", confidence=0.9),
            people_at_risk=RiskPrediction(count=1, confidence=0.8),
            required_response=[ResponseNeed(type="PUBLIC_WORKS_UTILITY", confidence=0.9)],
            entities=[],
            embedding_reference=None,
            overall_confidence=0.88,
            processing_status=ProcessingStatus.SUCCESS,
            warnings=[],
        )
    )
    ingestion_service = IngestionService(db=db_session, ml_adapter=mock_ml)

    new_report_payload = RawReportCreate(
        report_id="rep-test-ho-2",
        text="Minor puddle seen at Rasulgarh collapse area",
        source="simulator",
        is_synthetic=True,
        reported_at=datetime.now(timezone.utc),
    )
    ingest_result = ingestion_service.ingest_report(new_report_payload)
    assert ingest_result.incident_id == "inc-test-ho-prot"

    # Refresh incident and verify all operator fields are intact
    db_session.refresh(inc)
    assert inc.urgency == "CRITICAL"
    assert inc.incident_type == "STRUCTURAL_COLLAPSE"
    assert inc.people_at_risk_count == 10
    assert inc.location_text == "Locked Human Location"
    assert inc.priority_score == 95.0
    assert inc.priority_level == "CRITICAL"


# ==============================================================================
# 6. GET /incidents/{id}/timeline tests
# ==============================================================================

def test_get_timeline_events_and_ordering(client: TestClient, db_session: Session):
    """
    Timeline synthesizes REPORT_FUSED, PRIORITY_CALCULATED, STATUS_CHANGED, HUMAN_OVERRIDE.
    Does NOT contain citizen raw-text snippets.
    Supports asc and desc order.
    """
    seed_incident(db_session, "inc-test-tml-1", status="ACTIVE", priority_score=50.0)
    seed_report_and_link(db_session, "inc-test-tml-1", "rep-test-tml-1", text_content="Citizen says my house is under 4 feet of water")
    seed_priority_calc(db_session, "inc-test-tml-1", score=50.0, level="MEDIUM", explanation="Initial calc")

    # Add audit log for status change
    audit_status = AuditLog(
        override_id="ovr-test-tml-st",
        incident_id="inc-test-tml-1",
        operator_id="op_tml",
        field="status",
        previous_value="ACTIVE",
        new_value="VERIFIED",
        reason="Ground verification complete",
    )
    db_session.add(audit_status)

    # Add audit log for field override
    audit_field = AuditLog(
        override_id="ovr-test-tml-fld",
        incident_id="inc-test-tml-1",
        operator_id="op_tml",
        field="urgency",
        previous_value="MEDIUM",
        new_value="HIGH",
        reason="Field visual assessment",
    )
    db_session.add(audit_field)
    db_session.commit()

    # Query chronological timeline (asc)
    res_asc = client.get("/incidents/inc-test-tml-1/timeline?order=asc")
    assert res_asc.status_code == 200
    events = res_asc.json()["data"]["events"]
    assert len(events) == 4

    types = [e["event_type"] for e in events]
    assert "REPORT_FUSED" in types
    assert "PRIORITY_CALCULATED" in types
    assert "STATUS_CHANGED" in types
    assert "HUMAN_OVERRIDE" in types

    # Invariant: NO raw citizen text snippet in timeline
    for e in events:
        details_str = str(e["details"])
        assert "Citizen says my house is under 4 feet of water" not in details_str

    # Query reverse order (desc)
    res_desc = client.get("/incidents/inc-test-tml-1/timeline?order=desc")
    assert res_desc.status_code == 200
    events_desc = res_desc.json()["data"]["events"]
    assert events_desc[0]["timestamp"] >= events_desc[-1]["timestamp"]

    # Invalid order rejected with 422
    res_bad = client.get("/incidents/inc-test-tml-1/timeline?order=invalid_sort")
    assert res_bad.status_code == 422
