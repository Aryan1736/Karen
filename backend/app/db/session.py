"""
Karen's Ear — Database Session and Synchronous Engine Configuration
Uses SQLAlchemy 2.x and psycopg v3 exclusively.
"""
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import settings

# Synchronous engine using psycopg v3 via normalized postgresql+psycopg:// scheme
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a synchronous SQLAlchemy session.
    Closes the session after request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def dispose_engine() -> None:
    """
    Dispose of the connection pool used by the SQLAlchemy engine.
    Ensures all checked-in connections are closed cleanly on shutdown.
    """
    engine.dispose()
