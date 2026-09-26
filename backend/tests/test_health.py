"""
Karen's Ear — Health Endpoint & API Envelope Tests
Tests verify canonical response format, request tracing, and DB failure handling
without requiring an active database connection.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.app.core.config import Settings, mask_database_url
from backend.app.db.session import get_db
from backend.app.main import app


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_success(client: TestClient):
    """Verify GET /health returns 200 and canonical success envelope when database is reachable."""
    mock_session = MagicMock()
    # Mock successful SELECT 1 query
    mock_session.execute.return_value = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"] == {
            "status": "healthy",
            "database": "connected",
        }
        assert data["error"] is None
        assert isinstance(data["request_id"], str)
        assert data["request_id"].startswith("req-")
        assert data["timestamp"].endswith("Z")
        assert response.headers.get("x-request-id") == data["request_id"]
    finally:
        app.dependency_overrides.clear()


def test_health_db_failure(client: TestClient):
    """Verify GET /health returns 503 and canonical error envelope when database fails."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("Connection refused"))

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/health")
        assert response.status_code == 503

        data = response.json()
        assert data["success"] is False
        assert data["data"] is None
        assert data["error"]["code"] == "DATABASE_UNAVAILABLE"
        assert data["error"]["message"] == "Database connection failed"
        assert "password" not in str(data)
        assert isinstance(data["request_id"], str)
        assert data["request_id"].startswith("req-")
        assert data["timestamp"].endswith("Z")
        assert response.headers.get("x-request-id") == data["request_id"]
    finally:
        app.dependency_overrides.clear()


def test_health_accepts_incoming_request_id(client: TestClient):
    """Verify GET /health preserves client-supplied X-Request-Id header."""
    mock_session = MagicMock()
    mock_session.execute.return_value = MagicMock()

    custom_id = "test-trace-id-9988-aabb"
    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/health", headers={"X-Request-Id": custom_id})
        assert response.status_code == 200

        data = response.json()
        assert data["request_id"] == custom_id
        assert response.headers.get("x-request-id") == custom_id
    finally:
        app.dependency_overrides.clear()


def test_not_found_returns_canonical_envelope(client: TestClient):
    """Verify 404 responses conform strictly to canonical error envelope."""
    response = client.get("/non-existent-endpoint")
    assert response.status_code == 404

    data = response.json()
    assert data["success"] is False
    assert data["data"] is None
    assert data["error"]["code"] == "NOT_FOUND"
    assert isinstance(data["request_id"], str)
    assert data["timestamp"].endswith("Z")
    assert response.headers.get("x-request-id") == data["request_id"]


def test_database_url_normalization_and_masking():
    """Verify normalization to postgresql+psycopg:// and credential masking."""
    s1 = Settings(DATABASE_URL="postgresql://karen_user:secretpass123@db.render.com:5432/karendb")
    assert s1.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://karen_user:secretpass123@db.render.com:5432/karendb"
    assert "secretpass123" not in s1.get_masked_db_url()
    assert "secretpass123" not in repr(s1)
    assert "****" in s1.get_masked_db_url()

    s2 = Settings(DATABASE_URL="postgres://karen_user:secretpass123@localhost:5432/karendb")
    assert s2.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://karen_user:secretpass123@localhost:5432/karendb"

    s3 = Settings(DATABASE_URL="postgresql+psycopg://karen_user:secretpass123@localhost:5432/karendb")
    assert s3.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://karen_user:secretpass123@localhost:5432/karendb"

    masked = mask_database_url("postgresql://admin:super_secret@localhost:5432/db")
    assert "super_secret" not in masked
    assert "admin:****@localhost:5432/db" in masked


def test_settings_allow_extra_and_work_without_env_file():
    """Verify settings support Render environment (no .env file) and allow extra env vars."""
    s = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://render_user:pass@render_host:5432/render_db",
        HF_DATASET="LanD-FBK/crisitext",
        ML_MODEL_NAME="all-MiniLM-L6-v2",
        RENDER_SERVICE_ID="srv-12345",
    )
    assert s.DATABASE_URL == "postgresql://render_user:pass@render_host:5432/render_db"
    assert s.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://render_user:pass@render_host:5432/render_db"


def test_database_engine_and_base():
    """Verify SQLAlchemy 2.x engine configuration, psycopg v3 driver, and Base."""
    from sqlalchemy.orm import DeclarativeBase
    from backend.app.db.base import Base
    from backend.app.db.session import engine

    assert issubclass(Base, DeclarativeBase)
    assert len(Base.metadata.tables) in (0, 7)
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    assert engine.pool._pre_ping is True
