"""
Karen's Ear — Safe Transport & Leakage Firewall Unit Tests.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/api-contract.md (v1.0), DISASTER_SIMULATOR_ROADMAP.md
Status: Phase 4 — Safe Transport & Ingestion Bridge Test Suite
"""

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from simulator.models import (
    GroundTruth,
    GroundTruthIncidentType,
    GroundTruthRelationType,
    GroundTruthUrgency,
    LocationHint,
    LocationPrecision,
    RawReportPayload,
    ReportMetadata,
    ScenarioEvent,
)
from simulator.scenarios import get_scenario
from simulator.transport import (
    CircuitBreaker,
    CircuitState,
    GroundTruthLeakageError,
    RateLimiter,
    SafeTransport,
    TransportConfig,
    TransportResult,
    prepare_payload,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def flood_sample_event():
    return get_scenario("flood_rasulgarh")[3]  # evt-flood-004 (critical trapped van)


# =============================================================================
# 1. Pre-Flight Firewall Tests (Leak Prevention)
# =============================================================================

def test_prepare_payload_valid(flood_sample_event):
    payload = prepare_payload(flood_sample_event)

    assert payload["report_id"] == "rep-fld-004"
    assert payload["source"] == "simulator"
    assert payload["is_synthetic"] is True
    assert "trapped" in payload["text"].lower()

    # Strict ground truth absence
    forbidden = [
        "ground_truth",
        "incident_group",
        "expected_urgency",
        "expected_incident_type",
        "expected_people_at_risk",
        "expected_people_count",
        "relation_type",
        "expected_direction",
        "expected_needs_review",
        "notes",
    ]
    for key in forbidden:
        assert key not in payload
        if "metadata" in payload and isinstance(payload["metadata"], dict):
            assert key not in payload["metadata"]


def test_prepare_payload_rejects_non_synthetic():
    mock_event = MagicMock(spec=ScenarioEvent)
    mock_event.event_id = "evt-leak-01"
    mock_event.public_payload.return_value = {
        "report_id": "rep-leak-01",
        "text": "Flood alert",
        "source": "simulator",
        "is_synthetic": False,  # Safety breach
        "reported_at": "2026-09-26T18:00:00Z",
    }

    with pytest.raises(GroundTruthLeakageError, match="is_synthetic must be True"):
        prepare_payload(mock_event)


def test_prepare_payload_rejects_non_simulator_source():
    mock_event = MagicMock(spec=ScenarioEvent)
    mock_event.event_id = "evt-leak-02"
    mock_event.public_payload.return_value = {
        "report_id": "rep-leak-02",
        "text": "Flood alert",
        "source": "manual",  # Safety breach: must be simulator
        "is_synthetic": True,
        "reported_at": "2026-09-26T18:00:00Z",
    }

    with pytest.raises(GroundTruthLeakageError, match="source must be 'simulator'"):
        prepare_payload(mock_event)


def test_prepare_payload_rejects_ground_truth_in_payload():
    mock_event = MagicMock(spec=ScenarioEvent)
    mock_event.event_id = "evt-leak-03"
    mock_event.public_payload.return_value = {
        "report_id": "rep-leak-03",
        "text": "Flood alert",
        "source": "simulator",
        "is_synthetic": True,
        "reported_at": "2026-09-26T18:00:00Z",
        "expected_urgency": "CRITICAL",  # Leak
    }

    with pytest.raises(GroundTruthLeakageError, match="LEAKAGE VIOLATION"):
        prepare_payload(mock_event)


def test_prepare_payload_rejects_ground_truth_in_nested_metadata():
    mock_event = MagicMock(spec=ScenarioEvent)
    mock_event.event_id = "evt-leak-04"
    mock_event.public_payload.return_value = {
        "report_id": "rep-leak-04",
        "text": "Flood alert",
        "source": "simulator",
        "is_synthetic": True,
        "reported_at": "2026-09-26T18:00:00Z",
        "metadata": {
            "scenario_id": "flood_rasulgarh",
            "incident_group": "bbsr-flood-01",  # Leak inside metadata
        },
    }

    with pytest.raises(GroundTruthLeakageError, match="LEAKAGE VIOLATION"):
        prepare_payload(mock_event)


# =============================================================================
# 2. Circuit Breaker Tests
# =============================================================================

def test_circuit_breaker_transitions():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=0.1, success_threshold=2)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_attempt() is True

    # 2 failures do not trip
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    # 3rd failure trips circuit to OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_attempt() is False

    # Wait for recovery timeout
    import time
    time.sleep(0.12)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.can_attempt() is True

    # 1st success in half-open
    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN

    # 2nd success closes circuit
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_attempt() is True


# =============================================================================
# 3. Rate Limiter Tests
# =============================================================================

def test_rate_limiter_tokens():
    limiter = RateLimiter(rate_per_second=10.0, capacity=2.0)
    assert limiter.acquire(block=False) is True
    assert limiter.acquire(block=False) is True
    # Capacity exhausted
    assert limiter.acquire(block=False) is False


def test_rate_limiter_enforces_minimum_capacity():
    """R5.1: Enforces capacity >= 1.0 even when configured with sub-unit rate/capacity."""
    # Sub-unit capacity explicitly provided
    limiter = RateLimiter(rate_per_second=0.5, capacity=0.5)
    assert limiter.capacity == 1.0
    assert limiter.tokens == 1.0
    assert limiter.acquire(block=False) is True
    assert limiter.acquire(block=False) is False

    # Sub-unit rate with default capacity
    limiter_sub_rate = RateLimiter(rate_per_second=0.2)
    assert limiter_sub_rate.capacity == 1.0
    assert limiter_sub_rate.tokens == 1.0
    assert limiter_sub_rate.acquire(block=False) is True


def test_rate_limiter_acquire_blocking_no_deadlock():
    """R5.1: RateLimiter(rate_per_second=0.5, capacity=0.5) acquires without hanging."""
    import time
    # Fast rate to keep test execution fast
    limiter = RateLimiter(rate_per_second=50.0, capacity=0.5)
    assert limiter.capacity == 1.0

    # First acquire is immediate
    assert limiter.acquire(block=True) is True

    # Second acquire blocks briefly, refills tokens to >= 1.0, and succeeds
    t0 = time.monotonic()
    assert limiter.acquire(block=True) is True
    elapsed = time.monotonic() - t0
    assert elapsed < 0.5


# =============================================================================
# 4. Safe Transport Execution & Resilience Tests
# =============================================================================

def test_safe_transport_dry_run(flood_sample_event):
    config = TransportConfig(dry_run=True)
    transport = SafeTransport(config=config)

    res = transport.send_event(flood_sample_event)
    assert res.success is True
    assert res.status_code == 201
    assert res.buffered is False
    assert res.report_id == flood_sample_event.dispatch.report_id


def test_safe_transport_mock_successful_dispatch(flood_sample_event):
    def mock_server(payload):
        assert payload["is_synthetic"] is True
        assert payload["source"] == "simulator"
        return 201, {
            "success": True,
            "data": {
                "report_id": payload["report_id"],
                "status": "ACCEPTED",
                "relationship": "INITIAL",
            },
        }

    config = TransportConfig(dry_run=False, max_retries=0)
    transport = SafeTransport(config=config, mock_handler=mock_server)

    res = transport.send_event(flood_sample_event)
    assert res.success is True
    assert res.status_code == 201
    assert res.retries == 0
    assert transport.circuit_breaker.state == CircuitState.CLOSED


def test_safe_transport_retry_and_recovery(flood_sample_event):
    attempts = 0

    def flaky_server(payload):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionResetError("Temporary network blip")
        return 201, {"success": True, "status": "ACCEPTED"}

    config = TransportConfig(dry_run=False, max_retries=3, backoff_factor=0.01)
    transport = SafeTransport(config=config, mock_handler=flaky_server)

    res = transport.send_event(flood_sample_event)
    assert res.success is True
    assert res.retries == 2
    assert attempts == 3


def test_safe_transport_circuit_tripping_and_buffering(flood_sample_event):
    def dead_backend(payload):
        raise ConnectionRefusedError("Backend unreachable on port 8000")

    config = TransportConfig(
        dry_run=False,
        max_retries=0,
        buffer_on_failure=True,
    )
    transport = SafeTransport(config=config, mock_handler=dead_backend)
    # Configure low threshold for fast testing
    transport.circuit_breaker.failure_threshold = 2

    # Attempt 1: fails and buffers
    res1 = transport.send_event(flood_sample_event)
    assert res1.success is False
    assert res1.buffered is True
    assert transport.buffer_size == 1

    # Attempt 2: fails, trips circuit breaker, and buffers
    res2 = transport.send_event(flood_sample_event)
    assert res2.success is False
    assert res2.buffered is True
    assert transport.buffer_size == 2
    assert transport.circuit_breaker.state == CircuitState.OPEN

    # Attempt 3: fast-fails via open circuit breaker, buffers without network call
    res3 = transport.send_event(flood_sample_event)
    assert res3.success is False
    assert res3.buffered is True
    assert "Circuit breaker is OPEN" in res3.error
    assert transport.buffer_size == 3


def test_safe_transport_buffer_flush(flood_sample_event):
    server_healthy = False

    def dynamic_server(payload):
        if not server_healthy:
            raise ConnectionRefusedError("Offline")
        return 201, {"success": True, "status": "RECOVERED"}

    config = TransportConfig(dry_run=False, max_retries=0, buffer_on_failure=True)
    transport = SafeTransport(config=config, mock_handler=dynamic_server)

    # Dispatch while offline -> buffers 2 events
    transport.send_event(flood_sample_event)
    transport.send_event(flood_sample_event)
    assert transport.buffer_size == 2

    # Backend recovers
    server_healthy = True
    transport.circuit_breaker.reset()

    flush_results = transport.flush_buffer()
    assert len(flush_results) == 2
    assert all(r.success for r in flush_results)
    assert transport.buffer_size == 0


@pytest.mark.asyncio
async def test_safe_transport_async_dry_run(flood_sample_event):
    config = TransportConfig(dry_run=True)
    transport = SafeTransport(config=config)

    res = await transport.send_event_async(flood_sample_event)
    assert res.success is True
    assert res.status_code == 201


def test_transport_metrics(flood_sample_event):
    config = TransportConfig(dry_run=True)
    transport = SafeTransport(config=config)

    transport.send_event(flood_sample_event)
    transport.send_event(flood_sample_event)

    metrics = transport.get_metrics()
    assert metrics["total_dispatches"] == 2
    assert metrics["successful_dispatches"] == 2
    assert metrics["failed_dispatches"] == 0
    assert metrics["circuit_state"] == "CLOSED"
    assert "latency_p50_ms" in metrics
    assert "latency_p95_ms" in metrics
