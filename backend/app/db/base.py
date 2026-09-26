"""
Karen's Ear — SQLAlchemy Declarative Base
Foundation for SQLAlchemy 2.x ORM models.
DO NOT call Base.metadata.create_all() automatically on application startup.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy ORM models."""
    pass
