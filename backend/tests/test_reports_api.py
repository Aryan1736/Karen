"""
Karen's Ear — Reports Ingestion API Route Tests
Validates POST /reports contract compliance, canonical response envelopes,
request ID propagation, idempotency, and error handling.
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
from backend.app.models.incident import Incident
from backend.app.models.link import IncidentReportLink
from backend.app.models.ml import MLPrediction
from backend.app.models.report import RawReport
from backend.app.schemas.common import LocationPrecision, ProcessingStatus
from backend.app.schemas.ml import LocationPrediction, MLPredictionOutput, ResponseNeed, RiskPrediction, TypePrediction, UrgencyPrediction
from backend.app.services.ingestion import IngestionService
from backend.app.api.routes.reports import get_current_ingestion_service
from backend.app.services.ml_adapter import MLAdapter


def mock_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
    """Mock analyzer returning canonical ML prediction for API tests."""
    return MLPredictionOutput(
        report_id=report_id,
        model_version="mock-api-v1",
        incident_type=TypePrediction(label="FLOOD_FLASH_FLOOD", confidence=0.92),
        urgency=UrgencyPrediction(label="HIGH", confidence=0.88),
        location=LocationPrediction(
            text="Rasulgarh flyover",
            latitude=20.2961,
            longitude=85.8245,
            precision=LocationPrecision.APPROXIMATE,
            confidence=0.85,
        ),
        people_at_risk=RiskPrediction(count=2, confidence=0.85),
        required_response=[ResponseNeed(type="SEARCH_AND_RESCUE", confidence=0.9)],
        entities=[],
        embedding_reference=None,
        overall_confidence=0.88,
        processing_status=ProcessingStatus.SUCCESS,
        warnings=[],
    )


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides an isolated database session and cleans up test records."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(text("DELETE FROM incident_reports WHERE report_id LIKE 'rep-test-api-%'"))
        session.execute(text("DELETE FROM ml_predictions WHERE report_id LIKE 'rep-test-api-%'"))
        session.execute(text("DELETE FROM raw_reports WHERE report_id LIKE 'rep-test-api-%'"))
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


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient fixture with dependency overrides for database and ML adapter."""
    adapter = MLAdapter(analyzer=mock_analyzer)

    def override_get_db():
        yield db_session

    def override_get_ingestion_service():
        return IngestionService(db=db_session, ml_adapter=adapter)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_ingestion_service] = override_get_ingestion_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_post_reports_success_canonical_envelope(client: TestClient):
    """POST /reports returns HTTP 201 with canonical success envelope."""
    rep_id = f"rep-test-api-{uuid.uuid4().hex[:6]}"
    payload = {
        "report_id": rep_id,
        "text": "Flash flood warning at Rasulgarh flyover. Water level rising fast.",
        "source": "manual",
        "is_synthetic": False,
        "reported_at": "2026-09-26T14:35:00Z",
        "location_hint": {
            "raw_text": "Rasulgarh flyover",
            "latitude": 20.2961,
            "longitude": 85.8245,
            "precision": "approximate",
        },
        "metadata": {"caller_id": "+91-9876543210"},
    }

    response = client.post("/reports", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["success"] is True
    assert data["error"] is None
    assert isinstance(data["request_id"], str)
    assert data["request_id"].startswith("req-")
    assert data["timestamp"].endswith("Z")

    report_data = data["data"]
    assert report_data["report_id"] == rep_id
    assert isinstance(report_data["incident_id"], str)
    assert report_data["is_new_incident"] is True
    assert report_data["relationship"] == "INITIAL"
    assert report_data["processing_status"] == "SUCCESS"


def test_post_reports_client_request_id_tracing(client: TestClient):
    """X-Request-Id header is echoed in the response headers and envelope request_id."""
    rep_id = f"rep-test-api-{uuid.uuid4().hex[:6]}"
    custom_req_id = f"req-custom-{uuid.uuid4().hex[:8]}"

    payload = {
        "report_id": rep_id,
        "text": "Landslide blocking main road near Khandagiri.",
        "source": "manual",
        "is_synthetic": False,
        "reported_at": "2026-09-26T14:35:00Z",
    }

    headers = {"X-Request-Id": custom_req_id}
    response = client.post("/reports", json=payload, headers=headers)
    assert response.status_code == 201

    assert response.headers.get("x-request-id") == custom_req_id
    body = response.json()
    assert body["request_id"] == custom_req_id


def test_post_reports_validation_error_short_text(client: TestClient):
    """Reports with text < 3 characters return HTTP 422 with canonical error envelope."""
    payload = {
        "report_id": f"rep-test-api-{uuid.uuid4().hex[:6]}",
        "text": "Hi",  # 2 characters (below min 3)
        "source": "manual",
        "is_synthetic": False,
        "reported_at": "2026-09-26T14:35:00Z",
    }

    response = client.post("/reports", json=payload)
    assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["data"] is None
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any("text" in str(d) for d in data["error"]["details"])


def test_post_reports_validation_error_invalid_source(client: TestClient):
    """Reports with invalid source return HTTP 422 with canonical error envelope."""
    payload = {
        "report_id": f"rep-test-api-{uuid.uuid4().hex[:6]}",
        "text": "Valid distress text report.",
        "source": "unauthorized_carrier",
        "is_synthetic": False,
        "reported_at": "2026-09-26T14:35:00Z",
    }

    response = client.post("/reports", json=payload)
    assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_post_reports_idempotent_retry(client: TestClient):
    """Submitting identical payload twice returns HTTP 201 with same incident_id."""
    rep_id = f"rep-test-api-{uuid.uuid4().hex[:6]}"
    payload = {
        "report_id": rep_id,
        "text": "Structural damage reported at building 14.",
        "source": "manual",
        "is_synthetic": False,
        "reported_at": "2026-09-26T14:35:00Z",
    }

    res1 = client.post("/reports", json=payload)
    assert res1.status_code == 201
    inc_id_1 = res1.json()["data"]["incident_id"]

    res2 = client.post("/reports", json=payload)
    assert res2.status_code == 201
    inc_id_2 = res2.json()["data"]["incident_id"]

    assert inc_id_1 == inc_id_2
    assert res2.json()["data"]["is_new_incident"] is False


def test_post_reports_id_conflict_different_payload(client: TestClient):
    """Submitting same report_id with different payload returns HTTP 400 with REPORT_ID_CONFLICT."""
    rep_id = f"rep-test-api-{uuid.uuid4().hex[:6]}"
    payload_original = {
        "report_id": rep_id,
        "text": "Initial authentic dispatch text.",
        "source": "manual",
        "is_synthetic": False,
        "reported_at": "2026-09-26T14:35:00Z",
    }
    res1 = client.post("/reports", json=payload_original)
    assert res1.status_code == 201

    payload_tampered = {
        "report_id": rep_id,
        "text": "Tampered malicious dispatch text replacing original.",
        "source": "manual",
        "is_synthetic": False,
        "reported_at": "2026-09-26T14:35:00Z",
    }
    res2 = client.post("/reports", json=payload_tampered)
    assert res2.status_code == 400

    data = res2.json()
    assert data["success"] is False
    assert data["error"]["code"] == "REPORT_ID_CONFLICT"


def test_post_reports_simulator_dispatch(client: TestClient):
    """Simulator report is successfully ingested with is_synthetic: true."""
    rep_id = f"rep-test-api-{uuid.uuid4().hex[:6]}"
    payload = {
        "report_id": rep_id,
        "text": "Simulated flood pulse scenario 01 report.",
        "source": "simulator",
        "is_synthetic": True,
        "reported_at": "2026-09-26T14:35:00Z",
    }

    response = client.post("/reports", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["success"] is True
    assert data["data"]["report_id"] == rep_id


def test_post_reports_omitted_report_id_generates_canonical_id(client: TestClient, db_session: Session):
    """POST /reports with omitted report_id generates rep-<uuid> and uses it consistently."""
    generated_id = None
    try:
        payload = {
            "text": "Distress call with omitted report_id from citizen.",
            "source": "manual",
            "is_synthetic": False,
            "reported_at": "2026-09-26T14:35:00Z",
        }

        response = client.post("/reports", json=payload)
        assert response.status_code == 201

        body = response.json()
        assert body["success"] is True
        generated_id = body["data"]["report_id"]
        assert generated_id.startswith("rep-")

        # Verify ID consistency across all tables
        raw = db_session.get(RawReport, generated_id)
        assert raw is not None
        assert raw.report_id == generated_id

        pred = db_session.query(MLPrediction).filter(MLPrediction.report_id == generated_id).first()
        assert pred is not None
        assert pred.report_id == generated_id

        link = db_session.query(IncidentReportLink).filter(IncidentReportLink.report_id == generated_id).first()
        assert link is not None
        assert link.report_id == generated_id
        assert link.incident_id == body["data"]["incident_id"]
    finally:
        if generated_id:
            db_session.rollback()
            db_session.execute(text("DELETE FROM incident_reports WHERE report_id = :rid"), {"rid": generated_id})
            db_session.execute(text("DELETE FROM ml_predictions WHERE report_id = :rid"), {"rid": generated_id})
            db_session.execute(text("DELETE FROM raw_reports WHERE report_id = :rid"), {"rid": generated_id})
            db_session.commit()


def test_post_reports_empty_report_id_generates_canonical_id(client: TestClient, db_session: Session):
    """POST /reports with empty string report_id generates rep-<uuid> consistently."""
    generated_id = None
    try:
        payload = {
            "report_id": "",
            "text": "Distress call with empty report_id string.",
            "source": "manual",
            "is_synthetic": False,
            "reported_at": "2026-09-26T14:35:00Z",
        }

        response = client.post("/reports", json=payload)
        assert response.status_code == 201

        body = response.json()
        assert body["success"] is True
        generated_id = body["data"]["report_id"]
        assert generated_id.startswith("rep-")
        assert generated_id.strip() != ""

        # Verify ID consistency across all tables
        raw = db_session.get(RawReport, generated_id)
        assert raw is not None
        assert raw.report_id == generated_id

        pred = db_session.query(MLPrediction).filter(MLPrediction.report_id == generated_id).first()
        assert pred is not None
        assert pred.report_id == generated_id

        link = db_session.query(IncidentReportLink).filter(IncidentReportLink.report_id == generated_id).first()
        assert link is not None
        assert link.report_id == generated_id
    finally:
        if generated_id:
            db_session.rollback()
            db_session.execute(text("DELETE FROM incident_reports WHERE report_id = :rid"), {"rid": generated_id})
            db_session.execute(text("DELETE FROM ml_predictions WHERE report_id = :rid"), {"rid": generated_id})
            db_session.execute(text("DELETE FROM raw_reports WHERE report_id = :rid"), {"rid": generated_id})
            db_session.commit()


def test_post_reports_supplied_report_id_preserved(client: TestClient, db_session: Session):
    """POST /reports with client-supplied non-empty report_id preserves it across all tables."""
    rep_id = f"rep-test-api-pres-{uuid.uuid4().hex[:6]}"
    payload = {
        "report_id": rep_id,
        "text": "Report with non-empty client-supplied ID.",
        "source": "manual",
        "is_synthetic": False,
        "reported_at": "2026-09-26T14:35:00Z",
    }

    response = client.post("/reports", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert body["data"]["report_id"] == rep_id

    raw = db_session.get(RawReport, rep_id)
    assert raw is not None
    assert raw.report_id == rep_id

    pred = db_session.query(MLPrediction).filter(MLPrediction.report_id == rep_id).first()
    assert pred is not None
    assert pred.report_id == rep_id

    link = db_session.query(IncidentReportLink).filter(IncidentReportLink.report_id == rep_id).first()
    assert link is not None
    assert link.report_id == rep_id


def test_post_reports_simulator_rejected_when_not_synthetic(client: TestClient):
    """POST /reports with source 'simulator' and is_synthetic: false returns HTTP 422 VALIDATION_ERROR."""
    payload = {
        "report_id": f"rep-test-api-sim-fail-{uuid.uuid4().hex[:6]}",
        "text": "Simulated call but invalid is_synthetic flag.",
        "source": "simulator",
        "is_synthetic": False,
        "reported_at": "2026-09-26T14:35:00Z",
    }

    response = client.post("/reports", json=payload)
    assert response.status_code == 422

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any("simulator" in str(d) for d in body["error"]["details"])


def test_post_reports_manual_rejected_when_synthetic(client: TestClient):
    """POST /reports with source 'manual' and is_synthetic: true returns HTTP 422 VALIDATION_ERROR."""
    payload = {
        "report_id": f"rep-test-api-man-fail-{uuid.uuid4().hex[:6]}",
        "text": "Manual dispatch call but invalid is_synthetic flag.",
        "source": "manual",
        "is_synthetic": True,
        "reported_at": "2026-09-26T14:35:00Z",
    }

    response = client.post("/reports", json=payload)
    assert response.status_code == 422

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any("manual" in str(d) for d in body["error"]["details"])


def test_post_reports_partial_ml_routes_to_needs_review(client: TestClient, db_session: Session):
    """POST /reports with PARTIAL ML analysis routes incident to NEEDS_REVIEW while keeping PARTIAL processing_status."""
    rep_id = f"rep-test-api-part-{uuid.uuid4().hex[:6]}"

    def partial_mock_analyzer(text: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
        out = mock_analyzer(text, report_id, location_hint)
        out.processing_status = ProcessingStatus.PARTIAL
        return out

    # Override service with partial mock analyzer
    def override_partial_service():
        return IngestionService(db=db_session, ml_adapter=MLAdapter(analyzer=partial_mock_analyzer))

    app.dependency_overrides[get_current_ingestion_service] = override_partial_service

    try:
        payload = {
            "report_id": rep_id,
            "text": "Distress call resulting in partial ML extraction.",
            "source": "manual",
            "is_synthetic": False,
            "reported_at": "2026-09-26T14:35:00Z",
        }

        response = client.post("/reports", json=payload)
        assert response.status_code == 201

        body = response.json()
        assert body["data"]["report_id"] == rep_id
        assert body["data"]["processing_status"] == "PARTIAL"

        inc_id = body["data"]["incident_id"]
        inc = db_session.get(Incident, inc_id)
        assert inc is not None
        assert inc.status == "NEEDS_REVIEW"

        pred = db_session.query(MLPrediction).filter(MLPrediction.report_id == rep_id).first()
        assert pred is not None
        assert pred.processing_status == "PARTIAL"
    finally:
        app.dependency_overrides[get_current_ingestion_service] = lambda: IngestionService(
            db=db_session, ml_adapter=MLAdapter(analyzer=mock_analyzer)
        )

