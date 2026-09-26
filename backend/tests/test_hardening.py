"""
Karen's Ear — Production Hardening Verification Tests
Tests covering:
1. CORS configuration, preflight handling, credentials, and settings parsing.
2. SQLAlchemy engine pool disposal during FastAPI lifespan shutdown.
3. Privacy & logging cleanup (sanitized WebSocket malformed/unhandled frames & DB failures, LOG_LEVEL config).
4. Deployment concurrency safety check for single-worker in-memory WebSockets.
"""
from __future__ import annotations

import asyncio
import json
import logging
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from backend.app.core.config import Settings
from backend.app.core.logging import configure_logging
from backend.app.db.session import dispose_engine, engine, get_db
from backend.app.main import app, lifespan
from backend.app.services.websocket_manager import connection_manager


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


# ==============================================================================
# 1. CORS Tests
# ==============================================================================

def test_cors_default_allowed_origins(client: TestClient):
    """Verify safe development default origins receive Access-Control-Allow-Origin headers."""
    dev_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    for origin in dev_origins:
        response = client.get("/health", headers={"Origin": origin})
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_options_request(client: TestClient):
    """Verify preflight OPTIONS request for allowed origins returns 200 with CORS headers."""
    response = client.options(
        "/reports",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Request-Id",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in response.headers.get("access-control-allow-methods", "")


def test_cors_disallowed_origin_rejected(client: TestClient):
    """Verify untrusted/unconfigured origins do not receive CORS allow headers."""
    response = client.get("/health", headers={"Origin": "http://untrusted-external-site.com"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_exposes_request_id_header(client: TestClient):
    """Verify Access-Control-Expose-Headers allows frontend access to X-Request-Id."""
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    exposed = response.headers.get("access-control-expose-headers", "").lower()
    assert "x-request-id" in exposed


def test_cors_requests_without_origin_header_unaffected(client: TestClient):
    """Verify requests lacking an Origin header (e.g. server-to-server or CLI) work identically."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert response.json()["success"] is True


def test_cors_settings_parsing_comma_separated():
    """Verify Settings parses comma-separated CORS_ORIGINS environment string cleanly."""
    s = Settings(
        CORS_ORIGINS="https://app.karen.example.org, http://custom-preview.local:8080/",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
    )
    assert s.CORS_ORIGINS == [
        "https://app.karen.example.org",
        "http://custom-preview.local:8080",
    ]


def test_cors_settings_parsing_json_array():
    """Verify Settings parses JSON array string for CORS_ORIGINS."""
    s = Settings(
        CORS_ORIGINS='["https://admin.karen.org", "http://localhost:4000/"]',
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
    )
    assert s.CORS_ORIGINS == [
        "https://admin.karen.org",
        "http://localhost:4000",
    ]


def test_cors_settings_rejects_wildcard_origin():
    """Verify Settings disallows wildcard '*' origin when credentials are enabled."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            CORS_ORIGINS="*",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        )
    assert "Wildcard origin '*' is not permitted" in str(exc_info.value)


# ==============================================================================
# 2. Database Shutdown Cleanup Tests
# ==============================================================================

def test_dispose_engine_executes_cleanly():
    """Verify dispose_engine() invokes engine.dispose() without errors."""
    with patch.object(engine, "dispose", wraps=engine.dispose) as mock_dispose:
        dispose_engine()
        mock_dispose.assert_called_once()


def test_lifespan_disposes_engine_on_shutdown():
    """Verify FastAPI lifespan context manager disposes the engine on application exit."""
    saved_loop = connection_manager._loop
    async def _run():
        with patch("backend.app.main.dispose_engine") as mock_dispose:
            async with lifespan(app):
                pass
            mock_dispose.assert_called_once()

    try:
        asyncio.run(_run())
    finally:
        connection_manager._loop = saved_loop


# ==============================================================================
# 3. Logging & Privacy Cleanup Tests
# ==============================================================================

def test_ws_malformed_frame_does_not_log_raw_payload(client: TestClient, caplog: pytest.LogCaptureFixture):
    """Verify raw malformed WebSocket payload is absent from captured logs."""
    sensitive_token = "CRITICAL_OPERATOR_SECRET_KEY_12345"
    malformed_frame = f"MALFORMED_NON_JSON_{sensitive_token}{{{{bad"

    with caplog.at_level(logging.WARNING, logger="karen.backend.api.websockets"):
        with client.websocket_connect("/ws/events") as ws:
            ws.send_text(malformed_frame)
            import time
            time.sleep(0.05)

    # Raw secret must NOT appear anywhere in the captured logs
    assert sensitive_token not in caplog.text
    assert malformed_frame not in caplog.text
    # Safe operational diagnostic must be present
    assert "Malformed non-JSON client frame received over WebSocket" in caplog.text


def test_ws_unhandled_message_does_not_log_decoded_payload(client: TestClient, caplog: pytest.LogCaptureFixture):
    """Verify decoded unhandled WebSocket payload is absent from captured logs."""
    secret_payload_value = "TOP_SECRET_INCIDENT_FIELD_DATA_DO_NOT_LOG"
    unhandled_message = {
        "type": "UNKNOWN_CUSTOM_COMMAND",
        "secret_field": secret_payload_value,
        "detail": "Sensitive internal dispatch payload",
    }

    with caplog.at_level(logging.DEBUG, logger="karen.backend.api.websockets"):
        with client.websocket_connect("/ws/events") as ws:
            ws.send_text(json.dumps(unhandled_message))
            import time
            time.sleep(0.05)

    # Decoded unhandled message payload must NOT appear in captured logs
    assert secret_payload_value not in caplog.text
    assert "secret_field" not in caplog.text
    assert "Sensitive internal dispatch payload" not in caplog.text
    # Safe message type metadata must be present
    assert "Received unhandled client message type: UNKNOWN_CUSTOM_COMMAND" in caplog.text


def test_ws_non_dict_frame_does_not_log_raw_payload(client: TestClient, caplog: pytest.LogCaptureFixture):
    """Verify non-dict JSON frame does not leak raw payload into logs."""
    sensitive_item = "PRIVATE_EMBEDDED_RECORD_DATA"
    non_dict_json = json.dumps([sensitive_item, "item2"])

    with caplog.at_level(logging.DEBUG, logger="karen.backend.api.websockets"):
        with client.websocket_connect("/ws/events") as ws:
            ws.send_text(non_dict_json)
            import time
            time.sleep(0.05)

    # Raw item must NOT be logged
    assert sensitive_item not in caplog.text
    assert "Received non-dict JSON client frame of type: list" in caplog.text


def test_health_db_failure_does_not_log_raw_exception(client: TestClient, caplog: pytest.LogCaptureFixture):
    """Verify /health DB failure logs diagnostic exception class and request ID without raw error message."""
    sensitive_db_info = "password=secret_db_pass host=internal-db-cluster-01.render.internal"
    mock_session = MagicMock()
    mock_session.execute.side_effect = OperationalError("SELECT 1", {}, Exception(sensitive_db_info))

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        with caplog.at_level(logging.ERROR, logger="karen.backend"):
            response = client.get("/health")
            assert response.status_code == 503

        # Sensitive database text must NOT be in logs
        assert sensitive_db_info not in caplog.text
        assert "secret_db_pass" not in caplog.text
        assert "internal-db-cluster-01" not in caplog.text

        # Operational diagnostics must be present
        assert "Health check database probe failed: OperationalError" in caplog.text
        req_id = response.headers.get("x-request-id")
        assert req_id is not None
        assert f"[{req_id}]" in caplog.text
    finally:
        app.dependency_overrides.clear()


def test_configure_logging_applies_log_level():
    """Verify configure_logging applies configured level to karen logger tree."""
    configure_logging("DEBUG")
    karen_logger = logging.getLogger("karen")
    assert karen_logger.level == logging.DEBUG

    configure_logging("WARNING")
    assert karen_logger.level == logging.WARNING

    # Reset to INFO
    configure_logging("INFO")
    assert karen_logger.level == logging.INFO


def test_settings_log_level_validation():
    """Verify LOG_LEVEL validation normalizes casing and handles invalid levels."""
    s1 = Settings(LOG_LEVEL="debug", DATABASE_URL="postgresql://u:p@localhost/db")
    assert s1.LOG_LEVEL == "DEBUG"

    s2 = Settings(LOG_LEVEL="invalid_level", DATABASE_URL="postgresql://u:p@localhost/db")
    assert s2.LOG_LEVEL == "INFO"


# ==============================================================================
# 4. Deployment Safety Tests
# ==============================================================================

def test_lifespan_warns_on_multi_worker_concurrency(caplog: pytest.LogCaptureFixture):
    """Verify warning is logged if WEB_CONCURRENCY > 1 for single-worker in-memory WebSockets."""
    saved_loop = connection_manager._loop
    async def _run():
        with patch.dict("os.environ", {"WEB_CONCURRENCY": "2"}):
            with caplog.at_level(logging.WARNING, logger="karen.backend"):
                async with lifespan(app):
                    pass

    try:
        asyncio.run(_run())
    finally:
        connection_manager._loop = saved_loop
    assert "WEB_CONCURRENCY is set to 2" in caplog.text
    assert "in-memory WebSocket ConnectionManager and must be deployed with exactly 1 worker" in caplog.text
