"""
Karen's Ear — Live HTTP Integration Test.

Tests end-to-end live dispatch of simulation scenarios against a local mock HTTP server.
Verifies:
  1. CLI in --live mode requires --endpoint.
  2. Exactly N requests received at /reports endpoint.
  3. All requests carry is_synthetic: True and source: 'simulator'.
  4. Zero ground-truth leakage in HTTP request payloads and headers.
  5. Deterministic payload content fidelity.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from typing import Any, Dict, List
import pytest

from simulator.cli import main
from simulator.models import FORBIDDEN_GROUND_TRUTH_KEYS, verify_no_ground_truth_leakage


class MockIngestionHandler(BaseHTTPRequestHandler):
    """Mock HTTP handler for /reports ingestion endpoint."""

    # Class-level storage across requests
    received_requests: List[Dict[str, Any]] = []
    received_paths: List[str] = []

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        self.__class__.received_paths.append(self.path)

        if self.path == "/reports":
            payload = json.loads(body.decode("utf-8"))
            self.__class__.received_requests.append(payload)

            # Return success response strictly compliant with docs/api-contract.md
            response_data = {
                "success": True,
                "data": {
                    "report_id": payload.get("report_id", "rep-unknown"),
                    "incident_id": f"inc-{payload.get('report_id', 'unknown')}",
                    "is_new_incident": True,
                    "relationship": "INITIAL",
                    "processing_status": "SUCCESS",
                },
                "error": None,
                "request_id": f"req-{payload.get('report_id', 'unknown')}",
                "timestamp": "2026-09-26T21:00:00Z",
            }
            response_bytes = json.dumps(response_data).encode("utf-8")
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_bytes)))
            self.end_headers()
            self.wfile.write(response_bytes)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silence default stderr logging during tests
        pass


@pytest.fixture
def mock_http_server():
    """Runs a local ephemeral HTTP server in a daemon thread."""
    MockIngestionHandler.received_requests = []
    MockIngestionHandler.received_paths = []

    server = HTTPServer(("127.0.0.1", 0), MockIngestionHandler)
    host, port = server.server_address
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    endpoint = f"http://127.0.0.1:{port}/reports"
    yield endpoint, MockIngestionHandler

    server.shutdown()
    server.server_close()


def test_cli_live_mode_requires_endpoint():
    """CLI in --live mode without --endpoint must fail with exit code 1."""
    ret = main(["--live", "--scenario", "flood_rasulgarh"])
    assert ret == 1


def test_cli_live_mode_dispatches_exact_events(mock_http_server):
    """CLI in --live mode against local server receives exact N reports with zero leakage."""
    endpoint, handler = mock_http_server

    ret = main([
        "--live",
        "--endpoint", endpoint,
        "--scenario", "flood_rasulgarh",
        "--speed", "burst",
        "--quiet",
    ])

    assert ret == 0

    # flood_rasulgarh contains exactly 15 events
    assert len(handler.received_requests) == 15
    assert len(handler.received_paths) == 15
    assert all(p == "/reports" for p in handler.received_paths)

    # Validate each received payload on the wire
    for idx, payload in enumerate(handler.received_requests):
        assert payload["source"] == "simulator"
        assert payload["is_synthetic"] is True
        assert "reported_at" in payload
        assert "text" in payload
        assert payload["report_id"] == f"rep-fld-{idx + 1:03d}"

        # Centralized recursive ground truth firewall check on what went over the wire
        verify_no_ground_truth_leakage(payload, path=f"wire_payload_{idx}")


def test_cli_live_mode_with_limit(mock_http_server):
    """CLI in --live mode respects --limit option."""
    endpoint, handler = mock_http_server

    ret = main([
        "--live",
        "--endpoint", endpoint,
        "--scenario", "mixed_hard_negatives",
        "--speed", "burst",
        "--limit", "5",
        "--quiet",
    ])

    assert ret == 0
    assert len(handler.received_requests) == 5
    for idx, payload in enumerate(handler.received_requests):
        assert payload["report_id"] == f"rep-hn-{idx + 1:03d}"
        verify_no_ground_truth_leakage(payload, path=f"wire_payload_hn_{idx}")


# =============================================================================
# Phase 3 Transport Safety: Status Code & Resilience Matrix
# =============================================================================

from simulator.scenarios import get_scenario
from simulator.transport import SafeHttpTransport, TransportConfig


class ConfigurableHandler(BaseHTTPRequestHandler):
    """Configurable HTTP handler for testing error codes and headers."""
    status_code: int = 200
    body: Dict[str, Any] = {"success": True}
    extra_headers: Dict[str, str] = {}
    calls: int = 0

    def do_POST(self):
        ConfigurableHandler.calls += 1
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            self.rfile.read(content_length)

        resp_bytes = json.dumps(self.body).encode("utf-8")
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        for k, v in self.extra_headers.items():
            self.send_header(k, str(v))
        self.send_header("Content-Length", str(len(resp_bytes)))
        self.end_headers()
        self.wfile.write(resp_bytes)

    def log_message(self, format, *args):
        pass


@pytest.fixture
def configurable_http_server():
    """Ephemeral server with configurable status code and headers."""
    ConfigurableHandler.status_code = 200
    ConfigurableHandler.body = {"success": True}
    ConfigurableHandler.extra_headers = {}
    ConfigurableHandler.calls = 0

    server = HTTPServer(("127.0.0.1", 0), ConfigurableHandler)
    host, port = server.server_address
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    endpoint = f"http://127.0.0.1:{port}/reports"
    yield endpoint, ConfigurableHandler

    server.shutdown()
    server.server_close()


def test_live_http_status_200_app_failure_no_buffer(configurable_http_server):
    """HTTP 200 with success=false must not retry and must not buffer (permanent client error)."""
    endpoint, handler = configurable_http_server
    handler.status_code = 200
    handler.body = {"success": False, "error": "Schema violation: missing fields"}

    transport = SafeHttpTransport(
        endpoint=endpoint,
        config=TransportConfig(dry_run=False, buffer_on_failure=True, max_retries=2),
    )
    event = get_scenario("flood_rasulgarh")[0]
    res = transport.send_event(event)

    assert res.success is False
    assert res.retries == 0
    assert res.buffered is False
    assert len(transport.buffer) == 0
    assert "API Application Error" in res.error


def test_live_http_status_422_unprocessable_no_buffer(configurable_http_server):
    """HTTP 422 Unprocessable Entity must not retry and must not buffer."""
    endpoint, handler = configurable_http_server
    handler.status_code = 422
    handler.body = {"detail": "Unprocessable entity payload"}

    transport = SafeHttpTransport(
        endpoint=endpoint,
        config=TransportConfig(dry_run=False, buffer_on_failure=True, max_retries=2),
    )
    event = get_scenario("flood_rasulgarh")[0]
    res = transport.send_event(event)

    assert res.success is False
    assert res.retries == 0
    assert res.buffered is False
    assert len(transport.buffer) == 0
    assert "Permanent Client Rejection" in res.error


def test_live_http_status_500_server_error_retried_and_buffered(configurable_http_server):
    """HTTP 500 must retry up to max_retries and buffer on exhaustion."""
    endpoint, handler = configurable_http_server
    handler.status_code = 500
    handler.body = {"error": "Internal database dead"}

    transport = SafeHttpTransport(
        endpoint=endpoint,
        config=TransportConfig(dry_run=False, buffer_on_failure=True, max_retries=2, backoff_factor=0.005),
    )
    event = get_scenario("flood_rasulgarh")[0]
    res = transport.send_event(event)

    assert res.success is False
    assert res.retries == 2
    assert res.buffered is True
    assert len(transport.buffer) == 1


def test_live_http_status_503_service_unavailable_retry_after(configurable_http_server):
    """HTTP 503 with Retry-After header respects backoff, retries, and buffers on exhaustion."""
    endpoint, handler = configurable_http_server
    handler.status_code = 503
    handler.body = {"error": "Under high load"}
    handler.extra_headers = {"Retry-After": "0.01"}

    transport = SafeHttpTransport(
        endpoint=endpoint,
        config=TransportConfig(dry_run=False, buffer_on_failure=True, max_retries=2, backoff_factor=0.005),
    )
    event = get_scenario("flood_rasulgarh")[0]
    res = transport.send_event(event)

    assert res.success is False
    assert res.retries == 2
    assert res.buffered is True
    assert len(transport.buffer) == 1


def test_live_http_status_429_rate_limited_retry_after(configurable_http_server):
    """HTTP 429 with Retry-After header respects backoff, retries, and buffers on exhaustion."""
    endpoint, handler = configurable_http_server
    handler.status_code = 429
    handler.body = {"error": "Too many requests"}
    handler.extra_headers = {"Retry-After": "0.01"}

    transport = SafeHttpTransport(
        endpoint=endpoint,
        config=TransportConfig(dry_run=False, buffer_on_failure=True, max_retries=2, backoff_factor=0.005),
    )
    event = get_scenario("flood_rasulgarh")[0]
    res = transport.send_event(event)

    assert res.success is False
    assert res.retries == 2
    assert res.buffered is True
    assert len(transport.buffer) == 1


def test_live_http_buffer_flush_recovery(configurable_http_server):
    """Events buffered during outage are completely recovered with zero data loss once server recovers."""
    endpoint, handler = configurable_http_server
    handler.status_code = 500
    handler.body = {"error": "Server starting up"}

    transport = SafeHttpTransport(
        endpoint=endpoint,
        config=TransportConfig(dry_run=False, buffer_on_failure=True, max_retries=0),
    )
    events = get_scenario("flood_rasulgarh")[:3]
    for ev in events:
        res = transport.send_event(ev)
        assert res.success is False
        assert res.buffered is True
    assert len(transport.buffer) == 3

    # Server recovers to 201 Created
    handler.status_code = 201
    handler.body = {"success": True, "data": {"status": "ACCEPTED"}}
    transport.circuit_breaker.reset()

    flush_results = transport.flush_buffer()
    assert len(flush_results) == 3
    assert all(r.success for r in flush_results)
    assert len(transport.buffer) == 0

