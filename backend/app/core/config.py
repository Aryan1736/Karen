"""
Karen's Ear — Application Configuration & Settings
"""
import json
from pathlib import Path
from typing import Any, Union
from urllib.parse import urlparse
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_root() -> Path:
    """Resolve project root directory where root .env lives."""
    # backend/app/core/config.py -> core -> app -> backend -> project_root
    return Path(__file__).resolve().parent.parent.parent.parent


ROOT_DIR = get_project_root()
ENV_FILE = ROOT_DIR / ".env"


def mask_database_url(url: str) -> str:
    """Mask password in connection URI to prevent credential leakage."""
    try:
        parsed = urlparse(url)
        netloc = ""
        if parsed.username:
            netloc += parsed.username
            if parsed.password:
                netloc += ":****"
            netloc += "@"
        netloc += parsed.hostname or "localhost"
        if parsed.port:
            netloc += f":{parsed.port}"
        return f"{parsed.scheme}://{netloc}{parsed.path}"
    except Exception:
        return "<DATABASE_URL masked>"


def _parse_cors_origins_str(value: str) -> list[str]:
    """
    Parse CORS origins from a JSON array or comma-separated string:
    - Blank string -> []
    - String beginning '[' and ending ']':
        - Valid JSON list -> stripped list items
        - Malformed JSON -> fall back to comma-separated split
    - Every other string -> comma-separated split without trying json.loads()
    """
    stripped = value.strip()
    if not stripped:
        return []

    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [part.strip() for part in stripped.split(",") if part.strip()]

        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]

    return [part.strip() for part in stripped.split(",") if part.strip()]


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and/or root .env file.
    Non-backend variables (such as ML-specific variables or platform vars) are ignored.
    Works seamlessly in Render environments where .env is absent.
    """
    model_config = SettingsConfigDict(
        env_file=(str(ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "Karen's Ear Emergency Intelligence System"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # CORS Configuration
    CORS_ORIGINS: Union[list[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "https://tingle-sigma.vercel.app",
    ]

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/postgres"

    # Service Endpoints
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # Operational Engine Settings
    DUPLICATE_SIMILARITY_THRESHOLD: float = 0.85

    # ML Pipeline Runtime Mode
    ML_LIGHTWEIGHT_MODE: bool = False

    @field_validator("CORS_ORIGINS")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            origins = _parse_cors_origins_str(v)
        elif isinstance(v, (list, tuple, set)):
            origins = [str(item).strip() for item in v if str(item).strip()]
        else:
            return v

        if "*" in origins:
            raise ValueError(
                "Wildcard origin '*' is not permitted when credentials are enabled. "
                "Specify explicit origins instead."
            )
        return [o.rstrip("/") for o in origins]

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        upper = v.strip().upper()
        if upper not in valid_levels:
            return "INFO"
        return upper

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """
        Normalize DATABASE_URL internally to postgresql+psycopg:// for SQLAlchemy 2.x and psycopg v3.
        Supports standard postgresql:// and legacy postgres:// schemes.
        Never exposes raw credentials.
        """
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Alias for SQLALCHEMY_DATABASE_URI."""
        return self.SQLALCHEMY_DATABASE_URI

    def get_masked_db_url(self) -> str:
        """Return masked database connection URI safe for logs and diagnostics."""
        return mask_database_url(self.SQLALCHEMY_DATABASE_URI)

    def __repr__(self) -> str:
        return (
            f"Settings("
            f"APP_NAME={self.APP_NAME!r}, "
            f"ENVIRONMENT={self.ENVIRONMENT!r}, "
            f"DATABASE_URL={self.get_masked_db_url()!r}, "
            f"BACKEND_URL={self.BACKEND_URL!r}, "
            f"FRONTEND_URL={self.FRONTEND_URL!r}, "
            f"CORS_ORIGINS={self.CORS_ORIGINS!r}, "
            f"DUPLICATE_SIMILARITY_THRESHOLD={self.DUPLICATE_SIMILARITY_THRESHOLD}, "
            f"LOG_LEVEL={self.LOG_LEVEL!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


settings = Settings()
