"""
Karen's Ear — Disaster Simulator API Integration Tests
Tests /simulation/scenarios, /simulation/status, /simulation/pulse, /simulation/start, and /simulation/stop.
"""
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_get_simulation_scenarios():
    """Verify registered golden scenarios are returned with metadata."""
    res = client.get("/simulation/scenarios")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    scenarios = body["data"]
    assert len(scenarios) >= 2
    scenario_ids = [s["id"] for s in scenarios]
    assert "flood_rasulgarh" in scenario_ids
    assert "mixed_hard_negatives" in scenario_ids


def test_get_simulation_status():
    """Verify simulation telemetry status probe returns current playback state."""
    res = client.get("/simulation/status")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert "status" in data
    assert "reports_injected" in data


def test_simulation_pulse_injection():
    """Verify interactive single-step pulse injects into real ML and correlation pipeline."""
    res = client.post("/simulation/pulse", json={"scenario_id": "flood_rasulgarh"})
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["scenario_id"] == "flood_rasulgarh"
    assert "incident_id" in data
    assert "report_id" in data
    assert data["total_events"] == 15


def test_simulation_start_and_stop():
    """Verify starting and stopping a simulation run."""
    res = client.post("/simulation/start", json={
        "scenario_id": "flood_rasulgarh",
        "speed": "burst",
        "rate_per_minute": 15,
    })
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["status"] == "RUNNING"
    assert body["data"]["scenario_id"] == "flood_rasulgarh"

    # Immediately stop playback
    stop_res = client.post("/simulation/stop")
    assert stop_res.status_code == 200
    stop_body = stop_res.json()
    assert stop_body["success"] is True
    assert stop_body["data"]["status"] in ("STOPPED", "COMPLETED")
