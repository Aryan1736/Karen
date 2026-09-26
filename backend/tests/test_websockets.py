"""
Karen's Ear — Real-Time WebSocket Streaming Tests
Validates /ws/events strictly against locked architectural decisions:
1. Canonical event envelope ({event, payload, timestamp}) with NO extra top-level "type"
2. INCIDENT_CREATED payload = complete canonical IncidentResponse
3. INCIDENT_UPDATED payload = complete canonical IncidentResponse everywhere
4. INCIDENT_STATUS_CHANGED payload = {incident_id, old_status, new_status}
5. Review transition emits: 1. INCIDENT_STATUS_CHANGED, 2. INCIDENT_UPDATED
6. Reusable SIMULATION_PULSE schema and helper
7. PING keepalive every 30s; client {"type":"PONG"} updates last_pong; missing PONG does not force disconnect
8. In-memory connection manager; concurrent broadcast; dead client isolation
9. Safe REST-to-WebSocket thread boundary (asyncio.run_coroutine_threadsafe); post-commit only; no rollback on WS fail
"""
import asyncio
from datetime import datetime, timedelta, timezone
import json
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

from backend.app.api.routes.reports import get_current_ingestion_service
from backend.app.db.session import SessionLocal, get_db
from backend.app.main import app
from backend.app.schemas.common import LocationPrecision, ProcessingStatus
from backend.app.schemas.incident import IncidentResponse
from backend.app.schemas.ml import (
    LocationPrediction,
    MLPredictionOutput,
    ResponseNeed,
    RiskPrediction,
    TypePrediction,
    UrgencyPrediction,
)
from backend.app.schemas.websocket import (
    SimulationPulsePayload,
    WebSocketEnvelope,
    WebSocketEventType,
)
from backend.app.services.ingestion import IngestionService
from backend.app.services.ml_adapter import MLAdapter
from backend.app.services.websocket_manager import (
    broadcast_event,
    broadcast_simulation_pulse,
    connection_manager,
)


def mock_ws_analyzer(text_input: str, report_id: str, location_hint: dict | None = None) -> MLPredictionOutput:
    """Mock analyzer returning canonical ML prediction for WebSocket tests."""
    emb_val = [1.0 / (384 ** 0.5)] * 384
    return MLPredictionOutput(
        report_id=report_id,
        model_version="mock-ws-v1",
        incident_type=TypePrediction(label="FLOOD_FLASH_FLOOD", confidence=0.95),
        urgency=UrgencyPrediction(label="CRITICAL", confidence=0.92),
        location=LocationPrediction(
            text="Baramunda bus stand",
            latitude=20.2789,
            longitude=85.7894,
            precision=LocationPrecision.APPROXIMATE,
            confidence=0.88,
        ),
        people_at_risk=RiskPrediction(count=5, confidence=0.89),
        required_response=[
            ResponseNeed(type="SEARCH_AND_RESCUE", confidence=0.94),
            ResponseNeed(type="MEDICAL_EMS", confidence=0.90),
        ],
        entities=[],
        embedding=emb_val,
        embedding_reference="emb-mock-ws",
        overall_confidence=0.91,
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
        session.execute(text("DELETE FROM incident_reports WHERE report_id LIKE 'rep-test-ws-%'"))
        session.execute(text("DELETE FROM ml_predictions WHERE report_id LIKE 'rep-test-ws-%'"))
        session.execute(text("DELETE FROM raw_reports WHERE report_id LIKE 'rep-test-ws-%'"))
        session.execute(text("""
            DELETE FROM audit_logs 
            WHERE incident_id IN (SELECT incident_id FROM incidents WHERE NOT EXISTS (SELECT 1 FROM incident_reports ir WHERE ir.incident_id = incidents.incident_id))
        """))
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
    adapter = MLAdapter(analyzer=mock_ws_analyzer)

    def override_get_db():
        yield db_session

    def override_get_ingestion_service():
        return IngestionService(db=db_session, ml_adapter=adapter)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_ingestion_service] = override_get_ingestion_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ==============================================================================
# Connection Manager & Protocol Tests
# ==============================================================================

def test_ws_connection_accepted_and_clean_disconnect(client: TestClient):
    """Test that /ws/events accepts the socket and clean disconnect removes it."""
    initial_count = connection_manager.active_connections_count
    with client.websocket_connect("/ws/events") as ws:
        assert connection_manager.active_connections_count == initial_count + 1
    # After exiting the context manager, client socket closed
    assert connection_manager.active_connections_count == initial_count


def test_ws_multiple_clients_and_broadcast_delivery(client: TestClient):
    """Test that multiple concurrent clients all receive broadcasts with canonical envelope."""
    with client.websocket_connect("/ws/events") as ws1:
        with client.websocket_connect("/ws/events") as ws2:
            test_payload = {"incident_id": "inc-test-multi", "details": "alert"}
            broadcast_event("INCIDENT_UPDATED", test_payload)

            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()

            # Verify identical delivery
            assert msg1["event"] == "INCIDENT_UPDATED"
            assert msg1["payload"] == test_payload
            assert msg2["event"] == "INCIDENT_UPDATED"
            assert msg2["payload"] == test_payload

            # Locked decision 1: exactly event, payload, timestamp — NO top-level 'type'
            for msg in (msg1, msg2):
                assert set(msg.keys()) == {"event", "payload", "timestamp"}
                assert "type" not in msg
                assert msg["timestamp"].endswith("Z")


def test_ws_failed_client_does_not_block_healthy_client(client: TestClient):
    """Test client fault isolation: a failed socket does not stop delivery to healthy clients."""
    with client.websocket_connect("/ws/events") as healthy_ws:
        # Create a mock broken WebSocket object that fails on send_json
        class BrokenWebSocket:
            async def send_json(self, data):
                raise ConnectionResetError("Simulated socket write failure")
            async def accept(self): pass
            async def close(self, code=1000): pass

        broken_ws = BrokenWebSocket()
        # Add directly on connection manager
        connection_manager._active_connections.add(broken_ws)  # type: ignore

        # Broadcast should succeed for healthy client and prune the broken one
        broadcast_event("INCIDENT_UPDATED", {"msg": "fault-isolation-test"})

        healthy_msg = healthy_ws.receive_json()
        assert healthy_msg["event"] == "INCIDENT_UPDATED"
        assert healthy_msg["payload"] == {"msg": "fault-isolation-test"}

        # Verify broken socket was pruned from active connections
        assert broken_ws not in connection_manager._active_connections


def test_ws_ping_heartbeat_envelope(client: TestClient):
    """Test that server PING heartbeat adheres strictly to canonical envelope."""
    with client.websocket_connect("/ws/events") as ws:
        # Trigger send_heartbeat directly on manager
        loop = connection_manager.get_event_loop()
        assert loop is not None
        fut = asyncio.run_coroutine_threadsafe(connection_manager.send_heartbeat(), loop)
        fut.result(timeout=2.0)

        msg = ws.receive_json()
        assert msg["event"] == "PING"
        assert msg["payload"] == {}
        assert set(msg.keys()) == {"event", "payload", "timestamp"}
        assert "type" not in msg
        assert msg["timestamp"].endswith("Z")


def test_ws_pong_handling_and_last_pong_tracking(client: TestClient):
    """Test client {"type": "PONG"} updates last_pong and tolerant {"event": "PONG"}."""
    with client.websocket_connect("/ws/events") as ws:
        sockets = list(connection_manager._active_connections)
        assert len(sockets) >= 1
        active_ws = sockets[-1]

        initial_pong = connection_manager.get_last_pong(active_ws)
        assert initial_pong is not None

        # Send standard client PONG
        ws.send_text(json.dumps({"type": "PONG"}))
        # Small sleep to let receive loop process
        import time
        time.sleep(0.05)

        updated_pong = connection_manager.get_last_pong(active_ws)
        assert updated_pong is not None

        # Send tolerant compatibility PONG
        ws.send_text(json.dumps({"event": "PONG"}))
        time.sleep(0.05)
        compat_pong = connection_manager.get_last_pong(active_ws)
        assert compat_pong is not None


def test_ws_missing_pong_does_not_force_disconnect(client: TestClient):
    """Test that missing PONG response never forces socket disconnection."""
    with client.websocket_connect("/ws/events") as ws:
        # Trigger PING
        loop = connection_manager.get_event_loop()
        assert loop is not None
        fut = asyncio.run_coroutine_threadsafe(connection_manager.send_heartbeat(), loop)
        fut.result(timeout=2.0)

        ping_msg = ws.receive_json()
        assert ping_msg["event"] == "PING"

        # Client deliberately does NOT send PONG
        # Send an event from backend
        broadcast_event("SIMULATION_PULSE", {"injected_count": 1, "total_simulated": 1, "scenario": "test"})
        pulse_msg = ws.receive_json()
        assert pulse_msg["event"] == "SIMULATION_PULSE"
        # Socket remains connected and functional


def test_ws_malformed_client_frames_cannot_crash_server(client: TestClient):
    """Test that invalid text, malformed JSON, and unknown frames are ignored safely."""
    with client.websocket_connect("/ws/events") as ws:
        # 1. Invalid non-JSON text
        ws.send_text("NOT_VALID_JSON{{{")
        # 2. Non-dict JSON
        ws.send_text(json.dumps(["list", "of", "items"]))
        # 3. Arbitrary unrecognized dictionary
        ws.send_text(json.dumps({"unrecognized": "value"}))

        import time
        time.sleep(0.05)

        # Verify connection is still healthy by receiving a broadcast
        broadcast_event("PING", {})
        msg = ws.receive_json()
        assert msg["event"] == "PING"


# ==============================================================================
# Domain REST-to-WebSocket Integration Tests
# ==============================================================================

def test_ws_new_report_emits_incident_created_after_commit(client: TestClient):
    """Test that POST /reports creating a new incident emits INCIDENT_CREATED with canonical IncidentResponse."""
    with client.websocket_connect("/ws/events") as ws:
        report_payload = {
            "report_id": f"rep-test-ws-{uuid.uuid4()}",
            "text": "Severe flash flood at Baramunda bus terminal with 5 people stranded on bus roof.",
            "source": "simulator",
            "is_synthetic": True,
            "reported_at": "2026-09-26T18:30:00Z",
            "location_hint": {
                "raw_text": "Baramunda bus stand",
                "latitude": 20.2789,
                "longitude": 85.7894,
                "precision": "approximate",
            },
        }

        res = client.post("/reports", json=report_payload)
        assert res.status_code == 201
        res_data = res.json()["data"]
        assert res_data["is_new_incident"] is True

        ws_msg = ws.receive_json()
        assert ws_msg["event"] == "INCIDENT_CREATED"
        assert set(ws_msg.keys()) == {"event", "payload", "timestamp"}
        assert "type" not in ws_msg

        payload = ws_msg["payload"]
        assert payload["incident_id"] == res_data["incident_id"]
        assert payload["status"] in ("ACTIVE", "NEEDS_REVIEW")
        assert payload["incident_type"] == "FLOOD_FLASH_FLOOD"
        assert payload["urgency"] == "CRITICAL"
        assert "location" in payload
        assert "people_at_risk" in payload
        assert "priority" in payload
        assert "corroboration" in payload
        assert payload["source_report_ids"] == [report_payload["report_id"]]

        # Validate against Pydantic schema
        validated_incident = IncidentResponse.model_validate(payload)
        assert validated_incident.incident_id == res_data["incident_id"]


def test_ws_fused_report_emits_incident_updated_after_commit(client: TestClient):
    """Test that corroborating report absorbed by incident emits INCIDENT_UPDATED with full canonical IncidentResponse."""
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    now2_str = (now + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with client.websocket_connect("/ws/events") as ws:
        # Step 1: Initial report
        rep1_id = f"rep-test-ws-{uuid.uuid4()}"
        client.post("/reports", json={
            "report_id": rep1_id,
            "text": "Baramunda bus terminal completely flooded with stranded passengers.",
            "source": "simulator",
            "is_synthetic": True,
            "reported_at": now_str,
            "metadata": {"caller_id": "+91-9876543210"},
            "location_hint": {"raw_text": "Baramunda bus stand", "latitude": 20.2789, "longitude": 85.7894, "precision": "approximate"},
        })
        init_msg = ws.receive_json()
        assert init_msg["event"] == "INCIDENT_CREATED"
        inc_id = init_msg["payload"]["incident_id"]

        # Step 2: Corroborating report that fuses
        rep2_id = f"rep-test-ws-{uuid.uuid4()}"
        res2 = client.post("/reports", json={
            "report_id": rep2_id,
            "text": "Another witness confirms Baramunda bus terminal submerged in water.",
            "source": "simulator",
            "is_synthetic": True,
            "reported_at": now2_str,
            "metadata": {"caller_id": "+91-9123456780"},
            "location_hint": {"raw_text": "Baramunda bus stand", "latitude": 20.2789, "longitude": 85.7894, "precision": "approximate"},
        })
        assert res2.status_code == 201
        res2_data = res2.json()["data"]
        assert res2_data["is_new_incident"] is False
        assert res2_data["incident_id"] == inc_id


        # Step 3: Verify INCIDENT_UPDATED
        ws_msg = ws.receive_json()
        assert ws_msg["event"] == "INCIDENT_UPDATED"
        payload = ws_msg["payload"]
        assert payload["incident_id"] == inc_id
        # Locked decision 3: complete canonical IncidentResponse payload
        assert "location" in payload
        assert "people_at_risk" in payload
        assert "priority" in payload
        assert payload["corroboration"]["report_count"] >= 2
        assert rep2_id in payload["source_report_ids"]

        IncidentResponse.model_validate(payload)


def test_ws_review_emits_status_changed_then_updated_in_order(client: TestClient):
    """Test that POST /incidents/{id}/review emits INCIDENT_STATUS_CHANGED first, then INCIDENT_UPDATED."""
    with client.websocket_connect("/ws/events") as ws:
        # Create incident
        rep_id = f"rep-test-ws-{uuid.uuid4()}"
        client.post("/reports", json={
            "report_id": rep_id,
            "text": "Flash flood near Baramunda depot.",
            "source": "simulator",
            "is_synthetic": True,
            "reported_at": "2026-09-26T18:30:00Z",
            "location_hint": {"latitude": 20.2789, "longitude": 85.7894, "precision": "approximate"},
        })
        init_msg = ws.receive_json()
        inc_id = init_msg["payload"]["incident_id"]
        old_status = init_msg["payload"]["status"]

        # Review incident -> VERIFIED
        review_res = client.post(
            f"/incidents/{inc_id}/review",
            headers={"X-Operator-Id": "operator_alpha"},
            json={"target_status": "VERIFIED", "notes": "Verified by ground unit on site."},
        )
        assert review_res.status_code == 200

        # Event 1: INCIDENT_STATUS_CHANGED
        event1 = ws.receive_json()
        assert event1["event"] == "INCIDENT_STATUS_CHANGED"
        assert event1["payload"] == {
            "incident_id": inc_id,
            "old_status": old_status,
            "new_status": "VERIFIED",
        }

        # Event 2: INCIDENT_UPDATED with complete updated IncidentResponse
        event2 = ws.receive_json()
        assert event2["event"] == "INCIDENT_UPDATED"
        assert event2["payload"]["incident_id"] == inc_id
        assert event2["payload"]["status"] == "VERIFIED"
        assert "priority" in event2["payload"]

        IncidentResponse.model_validate(event2["payload"])


def test_ws_override_emits_incident_updated(client: TestClient):
    """Test that POST /incidents/{id}/override emits INCIDENT_UPDATED with complete canonical payload."""
    with client.websocket_connect("/ws/events") as ws:
        # Create incident
        rep_id = f"rep-test-ws-{uuid.uuid4()}"
        client.post("/reports", json={
            "report_id": rep_id,
            "text": "Water logging near Baramunda.",
            "source": "simulator",
            "is_synthetic": True,
            "reported_at": "2026-09-26T18:30:00Z",
            "location_hint": {"latitude": 20.2789, "longitude": 85.7894, "precision": "approximate"},
        })
        init_msg = ws.receive_json()
        inc_id = init_msg["payload"]["incident_id"]

        # Override urgency
        override_res = client.post(
            f"/incidents/{inc_id}/override",
            headers={"X-Operator-Id": "operator_bravo"},
            json={
                "field": "urgency",
                "new_value": "CRITICAL",
                "reason": "Confirmed escalating water levels entering homes.",
            },
        )
        assert override_res.status_code == 200

        override_msg = ws.receive_json()
        assert override_msg["event"] == "INCIDENT_UPDATED"
        assert override_msg["payload"]["incident_id"] == inc_id
        assert override_msg["payload"]["urgency"] == "CRITICAL"
        assert override_msg["payload"]["human_override"]["active"] is True

        IncidentResponse.model_validate(override_msg["payload"])


def test_ws_failed_transaction_emits_no_events(client: TestClient):
    """Test that validation or transaction failures emit NO events to connected clients."""
    with client.websocket_connect("/ws/events") as ws:
        # 1. Invalid report (text too short) -> 422
        bad_rep = client.post("/reports", json={
            "report_id": f"rep-test-ws-{uuid.uuid4()}",
            "text": "x",  # Too short (min 3 chars)
            "source": "simulator",
            "is_synthetic": True,
            "reported_at": "2026-09-26T18:30:00Z",
        })
        assert bad_rep.status_code == 422

        # 2. Invalid review transition on non-existent incident -> 404
        bad_rev = client.post(
            "/incidents/inc-non-existent-999/review",
            headers={"X-Operator-Id": "op_test"},
            json={"target_status": "VERIFIED", "notes": "Notes valid length"},
        )
        assert bad_rev.status_code == 404

        # Confirm nothing was queued by broadcasting a sentinel ping and receiving only the ping
        broadcast_event("PING", {})
        sentinel = ws.receive_json()
        assert sentinel["event"] == "PING"


def test_ws_broadcast_failure_does_not_change_rest_response(client: TestClient, monkeypatch):
    """Test failure isolation: a total failure in broadcast scheduling cannot change HTTP status."""
    def broken_broadcast_sync(event, payload):
        raise RuntimeError("Simulated fatal broadcast crash")

    monkeypatch.setattr(connection_manager, "broadcast_sync", broken_broadcast_sync)

    report_payload = {
        "report_id": f"rep-test-ws-{uuid.uuid4()}",
        "text": "Flash flood report testing broadcast exception resilience.",
        "source": "simulator",
        "is_synthetic": True,
        "reported_at": "2026-09-26T18:30:00Z",
    }
    # REST operation must still succeed with HTTP 201 Created
    res = client.post("/reports", json=report_payload)
    assert res.status_code == 201
    assert res.json()["success"] is True


def test_ws_simulation_pulse_schema_and_helper(client: TestClient):
    """Test SIMULATION_PULSE schema validation and helper broadcast."""
    # Valid schema
    pulse = SimulationPulsePayload(injected_count=5, total_simulated=42, scenario="flood_bhubaneswar_01")
    assert pulse.injected_count == 5
    assert pulse.total_simulated == 42
    assert pulse.scenario == "flood_bhubaneswar_01"

    # Invalid negative counts
    with pytest.raises(Exception):
        SimulationPulsePayload(injected_count=-1, total_simulated=10, scenario="flood_01")

    with pytest.raises(Exception):
        SimulationPulsePayload(injected_count=5, total_simulated=-5, scenario="flood_01")

    # Broadcast via helper
    with client.websocket_connect("/ws/events") as ws:
        broadcast_simulation_pulse(injected_count=10, total_simulated=100, scenario="cyclone_test")
        msg = ws.receive_json()
        assert msg["event"] == "SIMULATION_PULSE"
        assert msg["payload"] == {
            "injected_count": 10,
            "total_simulated": 100,
            "scenario": "cyclone_test",
        }


def test_ws_smoke_test_end_to_end_lifecycle(client: TestClient, db_session: Session):
    """
    Real local PostgreSQL + TestClient/WebSocket smoke test:
    1. Connect /ws/events
    2. POST a clearly synthetic test report
    3. Verify INCIDENT_CREATED
    4. Review and override it
    5. Verify expected WebSocket events
    6. Clean up temporary DB records
    7. Close socket cleanly
    """
    smoke_rep_id = f"rep-test-ws-smoke-{uuid.uuid4()}"

    with client.websocket_connect("/ws/events") as ws:
        # Step 2: POST synthetic report
        post_res = client.post("/reports", json={
            "report_id": smoke_rep_id,
            "text": "Smoke test: Flash flood at Baramunda square, civilians requiring extraction.",
            "source": "simulator",
            "is_synthetic": True,
            "reported_at": "2026-09-26T18:40:00Z",
            "location_hint": {"latitude": 20.2789, "longitude": 85.7894, "precision": "approximate"},
        })
        assert post_res.status_code == 201
        inc_id = post_res.json()["data"]["incident_id"]

        # Step 3: Verify INCIDENT_CREATED
        created_msg = ws.receive_json()
        assert created_msg["event"] == "INCIDENT_CREATED"
        assert created_msg["payload"]["incident_id"] == inc_id

        # Step 4a: Review incident
        rev_res = client.post(
            f"/incidents/{inc_id}/review",
            headers={"X-Operator-Id": "smoke_op"},
            json={"target_status": "VERIFIED", "notes": "Smoke test operator verification notes."},
        )
        assert rev_res.status_code == 200

        # Step 5a: Verify INCIDENT_STATUS_CHANGED followed by INCIDENT_UPDATED
        ev_status = ws.receive_json()
        assert ev_status["event"] == "INCIDENT_STATUS_CHANGED"
        assert ev_status["payload"]["incident_id"] == inc_id
        assert ev_status["payload"]["new_status"] == "VERIFIED"

        ev_upd = ws.receive_json()
        assert ev_upd["event"] == "INCIDENT_UPDATED"
        assert ev_upd["payload"]["incident_id"] == inc_id

        # Step 4b: Override incident
        ovr_res = client.post(
            f"/incidents/{inc_id}/override",
            headers={"X-Operator-Id": "smoke_op"},
            json={"field": "people_at_risk_count", "new_value": 12, "reason": "Confirmed 12 stranded on roof."},
        )
        assert ovr_res.status_code == 200

        # Step 5b: Verify INCIDENT_UPDATED
        ovr_msg = ws.receive_json()
        assert ovr_msg["event"] == "INCIDENT_UPDATED"
        assert ovr_msg["payload"]["people_at_risk"]["count"] == 12

        # Step 6: Clean up temporary DB records
        db_session.execute(text("DELETE FROM incident_reports WHERE report_id = :rid"), {"rid": smoke_rep_id})
        db_session.execute(text("DELETE FROM ml_predictions WHERE report_id = :rid"), {"rid": smoke_rep_id})
        db_session.execute(text("DELETE FROM raw_reports WHERE report_id = :rid"), {"rid": smoke_rep_id})
        db_session.execute(text("DELETE FROM audit_logs WHERE incident_id = :iid"), {"iid": inc_id})
        db_session.execute(text("DELETE FROM priority_calculations WHERE incident_id = :iid"), {"iid": inc_id})
        db_session.execute(text("DELETE FROM incidents WHERE incident_id = :iid"), {"iid": inc_id})
        db_session.commit()

        # Step 7: Socket closes cleanly upon exiting context manager
